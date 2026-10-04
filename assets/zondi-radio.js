// ZONDI RADIO FIXED v6.1 - Mic permission fix
window.initZondiRadio = function({socket, token, user, statusElId, feedElId}){
  const statusEl=document.getElementById(statusElId);
  const feedEl=document.getElementById(feedElId);
  const channelEl=document.getElementById('channel');
  const pttBtn=document.getElementById('ptt');
  let localStream=null, pcMap={}, isTalking=false;

  const log=(m)=>{
    const d=document.createElement('div'); d.className='mini';
    d.textContent='['+new Date().toLocaleTimeString()+'] '+m;
    d.style.padding='6px 0'; d.style.borderBottom='1px solid #222';
    if(feedEl) feedEl.prepend(d);
  };

  async function ensureMic(){
    if(localStream) return localStream;
    try{
      log('Requesting mic...');
      localStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      log('Mic granted ✅'); statusEl.textContent='Online • Mic OK'; return localStream;
    }catch(e){
      log('Mic blocked ❌ '+e.message); statusEl.textContent='Mic blocked - allow in settings';
      alert('Allow microphone then reload'); throw e;
    }
  }

  function joinChannel(){
    const ch=channelEl.value; socket.emit('join_channel',{channel:ch, auth:{token}});
    log('Joining channel '+ch);
  }
  channelEl.addEventListener('change', joinChannel);
  socket.on('connect',()=>{ statusEl.textContent='Online'; joinChannel(); ensureMic(); });
  socket.on('channel_joined',d=>{ statusEl.textContent='Channel '+d.channel+' clear'; });
  socket.on('ptt_granted',()=>{ statusEl.textContent='TALKING 🔴'; pttBtn.style.background='#22c55e'; isTalking=true; log('TALKING - speak now'); });
  socket.on('ptt_ended',d=>{ statusEl.textContent='Channel '+d.channel+' clear'; pttBtn.style.background=''; isTalking=false; log('Channel clear'); });
  socket.on('channel_busy',d=>{ log('Busy by '+d.busy_by); });

  socket.on('webrtc_offer', async data=>{
    await ensureMic();
    const pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
    localStream.getTracks().forEach(t=>pc.addTrack(t,localStream));
    pc.ontrack=ev=>{ const a=document.createElement('audio'); a.srcObject=ev.streams[0]; a.autoplay=true; document.body.appendChild(a); };
    pc.onicecandidate=ev=>{ if(ev.candidate) socket.emit('webrtc_ice',{target:data.from, channel:data.channel, candidate:ev.candidate, auth:{token}}); };
    await pc.setRemoteDescription(new RTCSessionDescription(data.description));
    const ans=await pc.createAnswer(); await pc.setLocalDescription(ans);
    socket.emit('webrtc_answer',{target:data.from, channel:data.channel, description:ans, auth:{token}});
    pcMap[data.from]=pc;
  });
  socket.on('webrtc_answer', async d=>{ const pc=pcMap[d.from]; if(pc) await pc.setRemoteDescription(new RTCSessionDescription(d.description)); });
  socket.on('webrtc_ice', async d=>{ const pc=pcMap[d.from]; if(pc&&d.candidate) try{await pc.addIceCandidate(d.candidate);}catch(e){} });
  socket.on('ptt_started', async data=>{
    if(data.sid===socket.id) return;
    log(data.name+' is talking...'); statusEl.textContent=data.name+' talking...';
    await ensureMic();
  });

  const startTalk=async(e)=>{ e.preventDefault(); try{await ensureMic();}catch{return;} socket.emit('ptt_start',{channel:channelEl.value, auth:{token}}); statusEl.textContent='Requesting channel...'; };
  const endTalk=(e)=>{ e.preventDefault(); if(isTalking) socket.emit('ptt_end',{channel:channelEl.value, auth:{token}}); };

  pttBtn.addEventListener('touchstart', startTalk, {passive:false});
  pttBtn.addEventListener('mousedown', startTalk);
  pttBtn.addEventListener('touchend', endTalk, {passive:false});
  pttBtn.addEventListener('mouseup', endTalk);
  pttBtn.addEventListener('mouseleave', endTalk);

  ensureMic(); log('Radio ready for '+user.email);
};
