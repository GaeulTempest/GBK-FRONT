import streamlit as st
import cv2
import av
import requests
import asyncio
import json
import uuid
import time
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
from cvzone.HandTrackingModule import HandDetector

# --- Konfigurasi dan Inisialisasi ---

# ==============================================================================
# PERBAIKI BAGIAN INI
# ==============================================================================
# GANTI URL DI BAWAH INI DENGAN URL PUBLIK DARI RAILWAY ANDA
# Pastikan URL HTTP menggunakan "https://"
# Pastikan URL WebSocket menggunakan "wss://" dan diakhiri dengan "/ws"

# Contoh URL dari Railway: gbk-backend-production-a1b2.up.railway.app

BACKEND_URL_HTTP = "https://gbk-backend-production-a1b2.up.railway.app"  # <-- GANTI INI
BACKEND_URL_WS = "wss://gbk-backend-production-a1b2.up.railway.app/ws"    # <-- GANTI INI
# ==============================================================================


# Inisialisasi detector tangan dari CVZone
detector = HandDetector(staticMode=False, maxHands=1, detectionCon=0.8, minTrackCon=0.5)

# Konfigurasi STUN server untuk WebRTC
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# --- Fungsi Helper ---

def classify_gesture(fingers: list) -> str:
    """Mengklasifikasikan gesture tangan berdasarkan jari yang terangkat."""
    if fingers == [0, 0, 0, 0, 0]:
        return "rock"
    if fingers == [1, 1, 1, 1, 1]:
        return "paper"
    if fingers == [0, 1, 1, 0, 0]:
        return "scissors"
    return "none"

# --- Callback untuk Memproses Frame Video ---

class VideoProcessor:
    def __init__(self):
        self.last_gesture = "none"
        self.last_detection_time = 0

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Fungsi ini dipanggil untuk setiap frame dari webcam."""
        img = frame.to_ndarray(format="bgr24")
        start_time = time.time()
        hands, img_processed = detector.findHands(img)
        detection_latency = (time.time() - start_time) * 1000
        st.session_state['detection_latency'] = f"{detection_latency:.2f} ms"

        if hands:
            hand = hands[0]
            fingers = detector.fingersUp(hand)
            gesture = classify_gesture(fingers)
            if gesture != "none":
                st.session_state['detected_gesture'] = gesture
                self.last_gesture = gesture
            cv2.putText(img_processed, self.last_gesture, (hand['bbox'][0], hand['bbox'][1] - 20),
                        cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
        
        return av.VideoFrame.from_ndarray(img_processed, format="bgr24")

# --- UI Aplikasi Streamlit ---

st.set_page_config(page_title="Gunting Batu Kertas Online", layout="centered")
st.title("🎮 Gunting Batu Kertas Online")

if 'player_id' not in st.session_state:
    st.session_state['player_id'] = str(uuid.uuid4())
if 'room_id' not in st.session_state:
    st.session_state['room_id'] = None
if 'game_started' not in st.session_state:
    st.session_state['game_started'] = False
if 'detected_gesture' not in st.session_state:
    st.session_state['detected_gesture'] = "none"
if 'game_result' not in st.session_state:
    st.session_state['game_result'] = None

if not st.session_state['room_id']:
    st.header("Lobby Permainan")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Buat Room Baru", use_container_width=True):
            try:
                # Permintaan untuk membuat room baru ke backend
                response = requests.post(f"{BACKEND_URL_HTTP}/create_room")
                if response.status_code == 200:
                    room_id = response.json()['room_id']
                    st.session_state['room_id'] = room_id
                    st.rerun()
                else:
                    st.error(f"Gagal membuat room. Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                st.error("Gagal membuat room. Server mungkin tidak aktif atau URL salah.")
                st.error(f"Detail: {e}")

    with col2:
        join_room_id = st.text_input("Masukkan Room ID untuk Bergabung", key="join_id")
        if st.button("Gabung Room", use_container_width=True):
            if join_room_id:
                st.session_state['room_id'] = join_room_id
                st.rerun()
            else:
                st.warning("Harap masukkan Room ID.")

else:
    st.header(f"Room: `{st.session_state['room_id']}`")
    st.write(f"ID Anda: `{st.session_state['player_id']}`")
    
    webrtc_ctx = webrtc_streamer(
        key="game-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        video_processor_factory=VideoProcessor,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

    st.info(f"Gesture Terdeteksi: **{st.session_state.get('detected_gesture', 'none').upper()}**")
    st.caption(f"Latency Deteksi: {st.session_state.get('detection_latency', '0 ms')}")

    if st.button("Kunci Gerakan!", use_container_width=True, type="primary"):
        gesture = st.session_state.get('detected_gesture', 'none')
        if gesture != "none" and webrtc_ctx.state.playing:
            
            async def send_and_receive():
                uri = f"{BACKEND_URL_WS}/{st.session_state['room_id']}/{st.session_state['player_id']}"
                try:
                    async with websockets.connect(uri) as websocket:
                        move_data = json.dumps({"type": "move", "move": gesture})
                        await websocket.send(move_data)
                        st.toast(f"Gerakan '{gesture}' terkirim!")
                        while True:
                            response = await websocket.recv()
                            message = json.loads(response)
                            if message.get("type") == "result":
                                st.session_state['game_result'] = message
                                break
                except Exception as e:
                    st.error(f"Koneksi WebSocket gagal: {e}")

            asyncio.run(send_and_receive())
            st.rerun()
        else:
            st.warning("Tidak ada gesture yang valid terdeteksi atau kamera tidak aktif.")

    if st.session_state['game_result']:
        result = st.session_state['game_result']
        winner = result.get('winner')
        moves = result.get('moves', {})
        
        st.subheader("Hasil Ronde")
        if winner == "draw":
            st.warning("Hasilnya Seri!")
        elif winner == st.session_state['player_id']:
            st.success("🎉 Anda Menang! 🎉")
        else:
            st.error("🤖 Anda Kalah! 🤖")
        
        for pid, move in moves.items():
            player_label = "Anda" if pid == st.session_state['player_id'] else "Lawan"
            st.write(f"Gerakan {player_label}: **{move.upper()}**")

        if st.button("Main Lagi?", use_container_width=True):
            st.session_state['game_result'] = None
            st.rerun()
