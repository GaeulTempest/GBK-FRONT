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
import websockets

# --- Konfigurasi dan Inisialisasi ---
# ==============================================================================
# PENTING: GANTI URL DI BAWAH INI DENGAN URL RAILWAY ANDA YANG BARU
# ==============================================================================
BACKEND_URL_HTTP = "https://gbk-production.up.railway.app"  # <-- GANTI INI
BACKEND_URL_WS = "wss://gbk-production.up.railway.app/ws"    # <-- GANTI INI
# ==============================================================================

# --- Inisialisasi Session State ---
if 'page' not in st.session_state:
    st.session_state.page = 'lobby'
if 'player_id' not in st.session_state:
    st.session_state.player_id = str(uuid.uuid4())
if 'room_id' not in st.session_state:
    st.session_state.room_id = None
if 'detected_gesture' not in st.session_state:
    st.session_state.detected_gesture = "none"
if 'game_result' not in st.session_state:
    st.session_state.game_result = None

# --- Halaman 1: LOBBY ---
def render_lobby():
    st.header("Selamat Datang di Gunting Batu Kertas!")
    st.subheader("Lobby Permainan")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Buat Room Baru", use_container_width=True, type="primary"):
            try:
                response = requests.post(f"{BACKEND_URL_HTTP}/create_room")
                if response.status_code == 200:
                    room_id = response.json().get('room_id')
                    st.session_state.room_id = room_id
                    st.session_state.page = 'waiting_room'
                    st.rerun()
                else:
                    st.error(f"Gagal membuat room. Status: {response.status_code}")
            except requests.exceptions.RequestException:
                st.error("Gagal terhubung ke server. Pastikan URL backend benar.")

    with col2:
        join_room_id = st.text_input("Masukkan Room ID untuk Bergabung", key="join_id")
        if st.button("Gabung Room", use_container_width=True):
            if join_room_id:
                st.session_state.room_id = join_room_id
                st.session_state.page = 'waiting_room'
                st.rerun()
            else:
                st.warning("Harap masukkan Room ID.")

# --- Halaman 2: RUANG TUNGGU ---
def render_waiting_room():
    st.subheader(f"Anda Berada di Room:")
    st.code(st.session_state.room_id, language=None)
    st.write("Bagikan ID di atas kepada teman Anda untuk bermain bersama.")
    st.info("Status: Menunggu pemain lain untuk bergabung...")
    
    if st.button("Mulai Permainan!", type="primary"):
        st.session_state.page = 'game_room'
        st.rerun()
        
    if st.button("Kembali ke Lobby"):
        st.session_state.page = 'lobby'
        st.session_state.room_id = None
        st.rerun()

# --- Halaman 3: ARENA PERMAINAN ---
def render_game_room():
    st.header(f"Arena Pertandingan - Room: `{st.session_state.room_id}`")
    
    detector = HandDetector(staticMode=False, maxHands=1, detectionCon=0.8, minTrackCon=0.5)
    RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

    class VideoProcessor:
        def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
            img = frame.to_ndarray(format="bgr24")
            hands, img_processed = detector.findHands(img)
            if hands:
                hand = hands[0]
                fingers = detector.fingersUp(hand)
                if fingers == [0, 0, 0, 0, 0]: gesture = "rock"
                elif fingers == [1, 1, 1, 1, 1]: gesture = "paper"
                elif fingers == [0, 1, 1, 0, 0]: gesture = "scissors"
                else: gesture = "none"
                st.session_state.detected_gesture = gesture
                cv2.putText(img_processed, gesture, (hand['bbox'][0], hand['bbox'][1] - 20), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
            return av.VideoFrame.from_ndarray(img_processed, format="bgr24")

    webrtc_streamer(
        key="game-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        video_processor_factory=VideoProcessor,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

    st.info(f"Gesture Terdeteksi: **{st.session_state.get('detected_gesture', 'none').upper()}**")

    if st.button("Kunci Gerakan!", use_container_width=True, type="primary"):
        gesture = st.session_state.get('detected_gesture', 'none')
        if gesture != "none":
            async def send_and_receive():
                uri = f"{BACKEND_URL_WS}/{st.session_state.room_id}/{st.session_state.player_id}"
                try:
                    async with websockets.connect(uri) as websocket:
                        move_data = json.dumps({"type": "move", "move": gesture})
                        await websocket.send(move_data)
                        st.toast(f"Gerakan '{gesture}' terkirim! Menunggu lawan...")
                        
                        response = await websocket.recv()
                        message = json.loads(response)
                        
                        if message.get("type") == "result":
                            st.session_state.game_result = message
                except Exception as e:
                    st.error(f"Koneksi WebSocket gagal: {e}")

            asyncio.run(send_and_receive())
            st.rerun()
        else:
            st.warning("Tidak ada gesture yang valid terdeteksi.")

    if st.session_state.game_result:
        result = st.session_state.game_result
        winner = result.get('winner')
        moves = result.get('moves', {})
        
        st.subheader("Hasil Ronde")
        if winner == "draw":
            st.warning("Hasilnya Seri!")
        elif winner == st.session_state.player_id:
            st.success("🎉 Anda Menang! 🎉")
        else:
            st.error("🤖 Anda Kalah! 🤖")
        
        for pid, move in moves.items():
            player_label = "Anda" if pid == st.session_state.player_id else "Lawan"
            st.write(f"Gerakan {player_label}: **{move.upper()}**")

        if st.button("Main Lagi?", use_container_width=True):
            st.session_state.game_result = None
            st.rerun()

    if st.button("Keluar dari Room"):
        st.session_state.page = 'lobby'
        st.session_state.room_id = None
        st.session_state.game_result = None
        st.rerun()

# --- Navigasi Utama Aplikasi ---
st.title("Gunting Batu Kertas Online 🏛️✂️📄")

if st.session_state.page == 'lobby':
    render_lobby()
elif st.session_state.page == 'waiting_room':
    render_waiting_room()
elif st.session_state.page == 'game_room':
    render_game_room()
