# Zondi Protect — Native Client App

This is the native Client companion for the existing Zondi web portals.

It adds **Protect Mode**, which requests the phone's foreground + background location permission and uses native background location updates to send the client's latest position to the existing Zondi API.

The app is intentionally separate from the Client/Patrol/Developer web portals:
- Web Zondi remains the portal system.
- Zondi Protect is the native Client layer for background location.
- Patrol continues to consume `/api/location/update` and the existing live/last-seen tracking.

## Backend

Default API:
`https://zondi-services-1.onrender.com`

Set `EXPO_PUBLIC_ZONDI_API_URL` when your Render hostname changes.

The native app uses:
- `POST /api/login`
- `POST /api/location/update`
- `POST /api/sos`

It stores the existing bearer token locally and sends it with background location updates.

## Create the Expo project

Use the current Expo project generator:

```bash
npx create-expo-app@latest zondi-protect
cd zondi-protect
```

Then install the native modules:

```bash
npx expo install expo-location expo-task-manager expo-secure-store expo-linking expo-intent-launcher expo-image expo-status-bar
```

Replace the generated `App.js` and `app.json` with the versions in this folder, then copy `assets/zondi-logo.png` into `assets/`.

Copy `.env.example` to `.env.local` if you need to change the API hostname.

## Development build

Background location is a native capability. Expo's documentation states that Android foreground/background location services are not available in Expo Go, so use a development build for this feature.

```bash
npx expo prebuild
npx expo run:android
```

For iOS on macOS:

```bash
npx expo prebuild
npx expo run:ios
```

## Android preview APK

After logging into EAS:

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --platform android --profile preview
```

The included `eas.json` sets the preview profile to generate an installable APK.

## Protect Mode behavior

When the user taps **Enable Protect Mode**:

1. Zondi checks whether Location Services are enabled.
2. It requests foreground location permission.
3. It requests background/Always location permission.
4. It starts native background location updates.
5. The newest location is sent to `/api/location/update`.
6. The Patrol Portal can show the user LIVE and retain the last known location when updates stop.

The app explicitly tells the user that the OS controls location access. Zondi does not bypass or secretly override system permissions.

## Important platform limitation

Background location works only while the phone's OS continues allowing the app's background location service. A user can still revoke Location permission or disable Location Services, and Zondi cannot override that system control.

Apple's Core Location system supports background location with the required background capability and Always/appropriate authorization. Android requires the appropriate background permission and, for continuous background location, a location foreground service on supported versions.

## Security notes

- The developer password is not stored in this app.
- Client authentication uses the existing Zondi API bearer token.
- Protect Mode stops when the client signs out.
- The server remains the authority for authorization.
