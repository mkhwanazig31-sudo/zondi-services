/* Zondi live radio transport: Socket.IO for control/signaling, WebRTC for audio. */
(function () {
  function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  window.initZondiRadio = function ({ socket, token, user, channelElId='channel', pttElId='ptt', statusElId='radioStatus', feedElId='radioFeed' } = {}) {
    const channelEl = document.getElementById(channelElId);
    const pttEl = document.getElementById(pttElId);
    const statusEl = document.getElementById(statusElId) || document.getElementById('status');
    const feedEl = document.getElementById(feedElId) || document.getElementById('feed');
    if (!socket || !token || !channelEl || !pttEl) return null;

    const auth = { token };
    const peers = new Map();
    const peerInfo = new Map();
    const remoteAudio = new Map();
    let localStream = null;
    let pressed = false;
    let requesting = false;
    let talking = false;
    let activeTalkerSid = null;
    let currentChannel = String(channelEl.value || '1');

    const rtcConfig = {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    };

    function status(text) { if (statusEl) statusEl.textContent = text; }
    function addFeed(text) {
      if (!feedEl) return;
      feedEl.insertAdjacentHTML('afterbegin', `<div class="item">🔊 ${esc(text)}</div>`);
    }
    function closePeer(sid) {
      const pc = peers.get(sid);
      if (pc) { try { pc.close(); } catch {} }
      peers.delete(sid);
      const audio = remoteAudio.get(sid);
      if (audio) { audio.pause(); audio.srcObject = null; audio.remove(); }
      remoteAudio.delete(sid);
    }
    function closeAllPeers() {
      [...peers.keys()].forEach(closePeer);
    }
    function resetRadio() {
      closeAllPeers();
      if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
        localStream = null;
      }
      activeTalkerSid = null;
      requesting = false;
      talking = false;
      pttEl.textContent = 'HOLD TO TALK';
    }
    function sendIce(target, candidate) {
      socket.emit('webrtc_ice', { channel: currentChannel, target, candidate, auth });
    }
    function makePeer(remoteSid, initiator) {
      if (!remoteSid || remoteSid === socket.id) return null;
      closePeer(remoteSid);
      const pc = new RTCPeerConnection(rtcConfig);
      peers.set(remoteSid, pc);
      pc.onicecandidate = e => { if (e.candidate) sendIce(remoteSid, e.candidate); };
      pc.onconnectionstatechange = () => {
        if (['failed','closed','disconnected'].includes(pc.connectionState)) closePeer(remoteSid);
      };
      pc.ontrack = e => {
        let audio = remoteAudio.get(remoteSid);
        if (!audio) {
          audio = document.createElement('audio');
          audio.autoplay = true;
          audio.playsInline = true;
          audio.setAttribute('aria-hidden', 'true');
          audio.style.display = 'none';
          document.body.appendChild(audio);
          remoteAudio.set(remoteSid, audio);
        }
        audio.srcObject = e.streams[0];
        audio.play().catch(() => {});
      };
      if (initiator && localStream) {
        localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
      }
      return pc;
    }
    async function offerPeer(remoteSid) {
      const pc = makePeer(remoteSid, true);
      if (!pc) return;
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      socket.emit('webrtc_offer', { channel: currentChannel, target: remoteSid, description: pc.localDescription, auth });
    }
    async function beginMedia() {
      if (!pressed || !talking) return;
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
          video: false
        });
        pttEl.textContent = 'RELEASE TO STOP';
        const targets = [...peerInfo.keys()].filter(sid => sid !== socket.id);
        await Promise.all(targets.map(offerPeer));
        status('Transmitting…');
      } catch (e) {
        socket.emit('ptt_end', { channel: currentChannel, auth });
        resetRadio();
        status('Microphone permission is required for PTT.');
      }
    }
    function startTalk() {
      if (requesting || talking) return;
      pressed = true;
      requesting = true;
      status('Requesting channel…');
      socket.emit('ptt_start', { channel: currentChannel, auth });
    }
    function endTalk() {
      pressed = false;
      if (!requesting && !talking) return;
      socket.emit('ptt_end', { channel: currentChannel, auth });
      resetRadio();
      status('Channel clear.');
    }

    socket.on('radio_peers', data => {
      if (String(data.channel) !== currentChannel) return;
      peerInfo.clear();
      (data.peers || []).forEach(p => peerInfo.set(String(p.sid), p));
    });
    socket.on('user_joined_channel', data => {
      if (String(data.channel) !== currentChannel || !data.sid || data.sid === socket.id) return;
      peerInfo.set(String(data.sid), data);
    });
    socket.on('user_left_channel', data => {
      if (String(data.channel) !== currentChannel) return;
      peerInfo.delete(String(data.sid));
      closePeer(String(data.sid));
    });
    socket.on('channel_joined', data => {
      currentChannel = String(data.channel);
      status('Channel ' + currentChannel + ' connected.');
    });
    socket.on('ptt_started', data => {
      if (String(data.channel) !== currentChannel) return;
      activeTalkerSid = data.sid || null;
      if (data.sid !== socket.id) {
        status((data.name || data.email || 'Patroller') + ' is talking…');
        addFeed((data.name || data.email || 'Patroller') + ' is speaking');
      }
    });
    socket.on('ptt_granted', async data => {
      if (String(data.channel) !== currentChannel || data.sid !== socket.id) return;
      requesting = false;
      if (!pressed) {
        socket.emit('ptt_end', { channel: currentChannel, auth });
        return;
      }
      talking = true;
      await beginMedia();
    });
    socket.on('ptt_denied', data => {
      requesting = false;
      talking = false;
      status(data.reason || 'PTT denied');
      pttEl.textContent = 'HOLD TO TALK';
    });
    socket.on('channel_busy', data => {
      requesting = false;
      talking = false;
      status('Channel busy: ' + (data.busy_by || 'another patroller'));
      pttEl.textContent = 'HOLD TO TALK';
    });
    socket.on('ptt_ended', data => {
      if (String(data.channel) !== currentChannel) return;
      activeTalkerSid = null;
      closeAllPeers();
      if (data.sid !== socket.id) status('Channel clear.');
    });
    socket.on('webrtc_offer', async data => {
      if (String(data.channel) !== currentChannel || !data.from || !data.description) return;
      activeTalkerSid = data.from;
      const pc = makePeer(String(data.from), false);
      if (!pc) return;
      try {
        await pc.setRemoteDescription(data.description);
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        socket.emit('webrtc_answer', { channel: currentChannel, target: data.from, description: pc.localDescription, auth });
        status((data.name || data.email || 'Patroller') + ' is talking…');
      } catch { closePeer(String(data.from)); }
    });
    socket.on('webrtc_answer', async data => {
      if (String(data.channel) !== currentChannel || !data.from || !data.description) return;
      const pc = peers.get(String(data.from));
      if (!pc) return;
      try { await pc.setRemoteDescription(data.description); } catch { closePeer(String(data.from)); }
    });
    socket.on('webrtc_ice', async data => {
      if (String(data.channel) !== currentChannel || !data.from || !data.candidate) return;
      const pc = peers.get(String(data.from));
      if (!pc) return;
      try { await pc.addIceCandidate(data.candidate); } catch {}
    });
    socket.on('disconnect', () => { resetRadio(); status('Offline'); });

    function switchChannel() {
      const next = String(channelEl.value || '1');
      if (next === currentChannel) return;
      if (requesting || talking) endTalk();
      socket.emit('leave_channel', { channel: currentChannel });
      peerInfo.clear();
      closeAllPeers();
      currentChannel = next;
      socket.emit('join_channel', { channel: currentChannel, auth });
      status('Joining channel ' + currentChannel + '…');
    }

    pttEl.onpointerdown = startTalk;
    pttEl.onpointerup = endTalk;
    pttEl.onpointercancel = endTalk;
    pttEl.onpointerleave = e => { if (pressed && e.buttons === 0) endTalk(); };
    channelEl.addEventListener('change', switchChannel);

    return { endTalk, reset: resetRadio };
  };
})();
