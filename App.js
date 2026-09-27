import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  AppState,
  Linking,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as Location from "expo-location";
import * as TaskManager from "expo-task-manager";
import * as SecureStore from "expo-secure-store";
import * as IntentLauncher from "expo-intent-launcher";
import { Image } from "expo-image";

const API_BASE =
  process.env.EXPO_PUBLIC_ZONDI_API_URL ||
  "https://zondi-services-1.onrender.com";

const LOCATION_TASK = "zondi-protect-background-location";

const COLORS = {
  bg: "#070707",
  surface: "#11100f",
  surface2: "#181613",
  line: "rgba(255,255,255,.09)",
  text: "#f8f5ee",
  muted: "#a9a39a",
  gold: "#d7a94a",
  gold2: "#f0c96c",
  green: "#22c55e",
  green2: "#63e08c",
  red: "#e64b4b",
  red2: "#ff6b62",
};

async function postLocation(location) {
  const token = await SecureStore.getItemAsync("zondi_token");
  if (!token) return false;

  const coords = location.coords;
  try {
    const response = await fetch(`${API_BASE}/api/location/update`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        lat: coords.latitude,
        lng: coords.longitude,
        accuracy: coords.accuracy,
        heading: coords.heading,
        speed: coords.speed,
      }),
    });

    if (!response.ok) return false;

    await SecureStore.setItemAsync("zondi_last_sync", new Date().toISOString());
    return true;
  } catch {
    return false;
  }
}

// MUST be global: background location tasks can run without mounting the UI.
TaskManager.defineTask(LOCATION_TASK, async ({ data, error }) => {
  if (error) return;

  const locations = data?.locations || [];
  if (!locations.length) return;

  // Send the newest position only so background batches do not create a burst.
  const latest = locations[locations.length - 1];
  await postLocation(latest);
});

async function isProtectRunning() {
  return Location.hasStartedLocationUpdatesAsync(LOCATION_TASK);
}

async function enableProtectMode() {
  const servicesEnabled = await Location.hasServicesEnabledAsync();
  if (!servicesEnabled) {
    if (Platform.OS === "android") {
      Alert.alert(
        "Location is off",
        "Turn on Location Services so Zondi can share your live position.",
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Open Settings",
            onPress: () =>
              IntentLauncher.startActivityAsync(
                IntentLauncher.ActivityAction.LOCATION_SOURCE_SETTINGS
              ),
          },
        ]
      );
    } else {
      Alert.alert(
        "Location is off",
        "Turn on Location Services in your phone settings, then return to Zondi."
      );
    }
    throw new Error("Location services are disabled.");
  }

  const foreground = await Location.requestForegroundPermissionsAsync();
  if (!foreground.granted) {
    throw new Error("Foreground location permission is required.");
  }

  const background = await Location.requestBackgroundPermissionsAsync();
  if (!background.granted) {
    Alert.alert(
      "Background permission needed",
      Platform.OS === "android"
        ? "Choose the background/always location option in system settings so Protect Mode can continue while the app is not on screen."
        : "Allow Zondi to use your location in the background so Protect Mode can continue while the app is not on screen.",
      [
        { text: "Not now", style: "cancel" },
        { text: "Open Settings", onPress: () => Linking.openSettings() },
      ]
    );
    throw new Error("Background location permission was not granted.");
  }

  await Location.startLocationUpdatesAsync(LOCATION_TASK, {
    accuracy: Location.Accuracy.High,
    timeInterval: 15000,
    distanceInterval: 20,
    pausesUpdatesAutomatically: false,
    showsBackgroundLocationIndicator: true,
    foregroundService: {
      notificationTitle: "Zondi Protect Mode",
      notificationBody: "Live location sharing is active for your authorized patrol team.",
      notificationColor: COLORS.gold,
      killServiceOnDestroy: false,
    },
  });

  // Send a first fix immediately.
  const current = await Location.getCurrentPositionAsync({
    accuracy: Location.Accuracy.High,
  });
  await postLocation(current);
}

async function disableProtectMode() {
  const running = await isProtectRunning();
  if (running) {
    await Location.stopLocationUpdatesAsync(LOCATION_TASK);
  }
}

async function getUser() {
  const raw = await SecureStore.getItemAsync("zondi_user");
  return raw ? JSON.parse(raw) : null;
}

async function getSessionToken() {
  return SecureStore.getItemAsync("zondi_token");
}

function Brand() {
  return (
    <View style={styles.brandRow}>
      <View style={styles.logoWrap}>
        <Image
          source={require("./assets/zondi-logo.png")}
          style={styles.logo}
          contentFit="cover"
        />
      </View>
      <View>
        <Text style={styles.brand}>ZONDI</Text>
        <Text style={styles.brandSub}>PROTECT MODE</Text>
      </View>
    </View>
  );
}

function Button({ title, onPress, variant = "default", disabled = false }) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.button,
        variant === "primary" && styles.buttonPrimary,
        variant === "green" && styles.buttonGreen,
        variant === "red" && styles.buttonRed,
        disabled && styles.buttonDisabled,
      ]}
    >
      <Text
        style={[
          styles.buttonText,
          (variant === "primary" || variant === "green" || variant === "red") &&
            styles.buttonTextDark,
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}

function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function login() {
    if (!email.trim() || !password) {
      Alert.alert("Missing details", "Enter your email and password.");
      return;
    }

    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Login failed.");
      }

      if (data.user?.role !== "client") {
        throw new Error(
          "Zondi Protect is for Client accounts. Approved patrol users should use the Patrol Portal."
        );
      }

      await SecureStore.setItemAsync("zondi_token", data.token);
      await SecureStore.setItemAsync(
        "zondi_user",
        JSON.stringify(data.user)
      );
      onLogin(data.user);
    } catch (error) {
      Alert.alert("Unable to sign in", error.message || "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.loginContainer}>
        <Brand />
        <View style={styles.heroCard}>
          <Text style={styles.heroEyebrow}>CLIENT SECURITY</Text>
          <Text style={styles.heroTitle}>Protect what matters.</Text>
          <Text style={styles.heroCopy}>
            Sign in once, then turn on Protect Mode when you need your
            authorized patrol team to keep receiving your live location.
          </Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Sign in</Text>
          <Text style={styles.label}>Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="you@example.com"
            placeholderTextColor="#6f6a63"
            style={styles.input}
          />
          <Text style={styles.label}>Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="Your password"
            placeholderTextColor="#6f6a63"
            style={styles.input}
          />
          <Button
            title={busy ? "Signing in…" : "Sign in"}
            onPress={login}
            variant="primary"
            disabled={busy}
          />
          <Button
            title="Forgot password"
            onPress={() => Linking.openURL(`${API_BASE}/forgot-password`)}
          />
        </View>

        <Text style={styles.footer}>Designed by G.V Mkhwanazi™</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function ProtectScreen({ user, onLogout }) {
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [locationServices, setLocationServices] = useState(true);

  async function refreshState() {
    try {
      setActive(await isProtectRunning());
      setLastSync(await SecureStore.getItemAsync("zondi_last_sync"));
      setLocationServices(await Location.hasServicesEnabledAsync());
    } catch {}
  }

  useEffect(() => {
    refreshState();
    const timer = setInterval(refreshState, 5000);
    const subscription = AppState.addEventListener("change", refreshState);
    return () => {
      clearInterval(timer);
      subscription.remove();
    };
  }, []);

  async function toggleProtect() {
    setBusy(true);
    try {
      if (active) {
        await disableProtectMode();
      } else {
        await enableProtectMode();
      }
      await refreshState();
    } catch (error) {
      Alert.alert(
        "Protect Mode",
        error.message || "Unable to change Protect Mode."
      );
      await refreshState();
    } finally {
      setBusy(false);
    }
  }

  async function sendSOS() {
    const token = await getSessionToken();
    if (!token) return;

    Alert.alert("Send emergency SOS?", "Your current location will be sent to the patrol network.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "SEND SOS",
        style: "destructive",
        onPress: async () => {
          try {
            const location = await Location.getCurrentPositionAsync({
              accuracy: Location.Accuracy.High,
            });
            const response = await fetch(`${API_BASE}/api/sos`, {
              method: "POST",
              headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                lat: location.coords.latitude,
                lng: location.coords.longitude,
              }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
              throw new Error(data.error || "SOS failed.");
            }
            Alert.alert("SOS sent", "The patrol network has received your emergency alert.");
          } catch (error) {
            Alert.alert("SOS failed", error.message || "Unable to send SOS.");
          }
        },
      },
    ]);
  }

  async function logout() {
    await disableProtectMode().catch(() => {});
    await SecureStore.deleteItemAsync("zondi_token");
    await SecureStore.deleteItemAsync("zondi_user");
    await SecureStore.deleteItemAsync("zondi_last_sync");
    onLogout();
  }

  const statusTitle = active ? "PROTECT MODE ACTIVE" : "PROTECT MODE OFF";
  const statusCopy = active
    ? "Zondi is sharing your location in the background with your authorized patrol network."
    : "Turn this on when you need Zondi to keep sharing your location while the app is not on screen.";

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.page}>
        <View style={styles.header}>
          <Brand />
          <Button title="Sign out" onPress={logout} />
        </View>

        <View style={styles.heroCard}>
          <Text style={styles.heroEyebrow}>WELCOME BACK</Text>
          <Text style={styles.heroTitle}>
            {user?.name || user?.email || "Client"}
          </Text>
          <Text style={styles.heroCopy}>
            Your Zondi protection controls are ready.
          </Text>
        </View>

        <View style={[styles.protectCard, active && styles.protectCardActive]}>
          <View style={styles.protectTop}>
            <View>
              <Text style={styles.heroEyebrow}>LOCATION PROTECTION</Text>
              <Text style={styles.protectTitle}>{statusTitle}</Text>
            </View>
            <View style={[styles.statusDot, active && styles.statusDotActive]} />
          </View>

          <Text style={styles.heroCopy}>{statusCopy}</Text>

          <Button
            title={
              busy
                ? "Updating…"
                : active
                ? "Turn Protect Mode Off"
                : "Enable Protect Mode"
            }
            onPress={toggleProtect}
            variant={active ? "red" : "primary"}
            disabled={busy}
          />

          <View style={styles.permissionRow}>
            <Text style={styles.permissionLabel}>Phone Location</Text>
            <Text style={styles.permissionValue}>
              {locationServices ? "Available" : "OFF"}
            </Text>
          </View>
          <View style={styles.permissionRow}>
            <Text style={styles.permissionLabel}>Background access</Text>
            <Text style={styles.permissionValue}>
              {active ? "Enabled" : "Not running"}
            </Text>
          </View>
          <View style={styles.permissionRow}>
            <Text style={styles.permissionLabel}>Last sync</Text>
            <Text style={styles.permissionValue}>
              {lastSync ? new Date(lastSync).toLocaleTimeString() : "Not yet"}
            </Text>
          </View>
        </View>

        <View style={styles.gridRow}>
          <View style={[styles.card, styles.gridHalf]}>
            <Text style={styles.sectionTitle}>How it works</Text>
            <Text style={styles.bodyText}>
              When Protect Mode is enabled, the phone's operating system
              provides background location updates. Zondi sends the newest
              position to your server, so Patrol can show LIVE or LAST SEEN.
            </Text>
          </View>

          <View style={[styles.card, styles.gridHalf]}>
            <Text style={styles.sectionTitle}>Emergency</Text>
            <Text style={styles.bodyText}>
              Send an SOS with your current position directly to the Zondi
              patrol network.
            </Text>
            <Button title="🚨 SEND SOS" onPress={sendSOS} variant="red" />
          </View>
        </View>

        <View style={styles.notice}>
          <Text style={styles.noticeTitle}>SYSTEM CONTROL</Text>
          <Text style={styles.noticeText}>
            Zondi never bypasses phone permissions. If Location Services are
            turned off or background permission is revoked, Patrol will keep
            the last known position and show the signal as unavailable.
          </Text>
        </View>

        <Text style={styles.footer}>Designed by G.V Mkhwanazi™</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const savedUser = await getUser();
      const token = await getSessionToken();
      if (savedUser && token) setUser(savedUser);
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.screen}>
        <View style={styles.loading}>
          <Brand />
          <Text style={styles.mini}>Loading secure session…</Text>
        </View>
      </SafeAreaView>
    );
  }

  return user ? (
    <ProtectScreen user={user} onLogout={() => setUser(null)} />
  ) : (
    <LoginScreen onLogin={setUser} />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.bg },
  page: { padding: 20, paddingBottom: 42 },
  loginContainer: { padding: 20, paddingTop: 46, paddingBottom: 40 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  logoWrap: {
    width: 48,
    height: 48,
    borderRadius: 15,
    overflow: "hidden",
    backgroundColor: "#000",
    borderWidth: 1,
    borderColor: "rgba(215,169,74,.35)",
  },
  logo: { width: "100%", height: "100%" },
  brand: { color: COLORS.text, fontWeight: "900", letterSpacing: 3, fontSize: 15 },
  brandSub: { color: COLORS.muted, fontSize: 9, letterSpacing: 1.1, marginTop: 3 },
  heroCard: {
    marginTop: 16,
    padding: 22,
    backgroundColor: COLORS.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: COLORS.line,
  },
  heroEyebrow: {
    color: COLORS.gold2,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1.6,
  },
  heroTitle: {
    color: COLORS.text,
    fontSize: 34,
    fontWeight: "900",
    letterSpacing: -1.2,
    marginTop: 7,
  },
  heroCopy: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 19,
    marginTop: 8,
  },
  card: {
    marginTop: 14,
    padding: 19,
    backgroundColor: COLORS.surface,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: COLORS.line,
  },
  sectionTitle: {
    color: COLORS.text,
    fontSize: 16,
    fontWeight: "900",
    marginBottom: 8,
  },
  label: {
    color: COLORS.muted,
    fontSize: 11,
    fontWeight: "800",
    marginTop: 12,
    marginBottom: 6,
  },
  input: {
    minHeight: 50,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "#0b0a09",
    color: COLORS.text,
    paddingHorizontal: 13,
    fontSize: 14,
  },
  button: {
    minHeight: 45,
    paddingHorizontal: 15,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "#191714",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },
  buttonPrimary: {
    backgroundColor: COLORS.gold,
    borderColor: COLORS.gold,
  },
  buttonGreen: {
    backgroundColor: COLORS.green,
    borderColor: COLORS.green,
  },
  buttonRed: {
    backgroundColor: COLORS.red,
    borderColor: COLORS.red,
  },
  buttonDisabled: { opacity: 0.55 },
  buttonText: { color: COLORS.text, fontWeight: "900", fontSize: 12 },
  buttonTextDark: { color: "#1b1204" },
  protectCard: {
    marginTop: 14,
    padding: 21,
    borderRadius: 24,
    backgroundColor: "#11100f",
    borderWidth: 1,
    borderColor: "rgba(215,169,74,.24)",
  },
  protectCardActive: {
    borderColor: "rgba(34,197,94,.38)",
    shadowColor: COLORS.green,
    shadowOpacity: 0.18,
    shadowRadius: 22,
    elevation: 8,
  },
  protectTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  protectTitle: {
    color: COLORS.text,
    fontSize: 24,
    fontWeight: "900",
    marginTop: 5,
  },
  statusDot: {
    width: 14,
    height: 14,
    borderRadius: 99,
    backgroundColor: "#57534e",
  },
  statusDotActive: { backgroundColor: COLORS.green, shadowColor: COLORS.green, shadowOpacity: 0.9, shadowRadius: 10 },
  permissionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 10,
    paddingTop: 11,
    marginTop: 11,
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,.05)",
  },
  permissionLabel: { color: COLORS.muted, fontSize: 11 },
  permissionValue: { color: COLORS.text, fontWeight: "800", fontSize: 11 },
  gridRow: { gap: 0 },
  gridHalf: { width: "100%" },
  bodyText: { color: COLORS.muted, fontSize: 11, lineHeight: 18 },
  notice: {
    marginTop: 14,
    padding: 16,
    borderLeftWidth: 3,
    borderLeftColor: COLORS.gold,
    backgroundColor: "rgba(215,169,74,.07)",
    borderRadius: 12,
  },
  noticeTitle: { color: COLORS.gold2, fontSize: 10, fontWeight: "900", letterSpacing: 1.3 },
  noticeText: { color: "#ead5a0", fontSize: 10, lineHeight: 16, marginTop: 6 },
  mini: { color: COLORS.muted, fontSize: 11, marginTop: 10 },
  footer: {
    textAlign: "center",
    color: "#7f7970",
    fontSize: 10,
    letterSpacing: 0.7,
    marginTop: 25,
  },
  loading: { flex: 1, alignItems: "center", justifyContent: "center" },
});
