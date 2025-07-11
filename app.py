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
# Pastikan URL ini sudah benar sesuai dengan dashboard Railway Anda
BACKEND_URL_HTTP = "https://gbk-backend-production-1234.up.railway.app" # <-- GANTI SESUAI URL ANDA
BACKEND_URL_WS = "wss://gbk-backend-production-1234.up.railway.app/ws"   # <-- GANTI SESUAI URL ANDA

# --- Inisialisasi Session State ---
# Variabel untuk mengelola halaman yang ditampilkan
if 'page' not in st.session_state:
    st.session_state.page = 'lobby'
if 'player_id' not in st.session_state:
    st.session_state['player_id'] = str(uuid.uuid4())
if 'room_id' not in st.session_state:
    st.session_state['room_id'] = None
if 'detected_gesture' not in st.session_state:
    st.session_state['detected_gesture'] = "none"
if 'game_result' not in st.session_state:
    st.session_state['game_result'] = None

# =====================================================================
# BAGIAN Halaman 1: LOBBY
# =====================================================================
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
                    st.session_state['room_id'] = room_id
                    st.session_state.page = 'waiting_room' # Pindah ke halaman ruang tunggu
                    st.rerun()
                else:
                    st.error(f"Gagal membuat room. Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                st.error("Gagal terhubung ke server. Pastikan URL backend benar.")

    with col2:
        join_room_id = st.text_input("Masukkan Room ID untuk Bergabung", key="join_id")
        if st.button("Gabung Room", use_container_width=True):
            if join_room_id:
                st.session_state['room_id'] = join_room_id
                st.session_state.page = 'waiting_room' # Pindah ke halaman ruang tunggu
                st.rerun()
            else:
                st.warning("Harap masukkan Room ID.")

# =====================================================================
# BAGIAN Halaman 2: RUANG TUNGGU
# =====================================================================
def render_waiting_room():
    st.subheader(f"Anda Berada di Room: `{st.session_state.room_id}`")
    st.write("Bagikan ID di atas kepada teman Anda untuk bermain bersama.")
    st.info("Status: Menunggu pemain lain untuk bergabung...")
    
    # Placeholder untuk jumlah pemain yang terhubung
    players_connected = st.empty()
    players_connected.write("Pemain terhubung: 1/2")

    # Tombol untuk kembali ke lobby
    if st.button("Kembali ke Lobby"):
        st.session_state.page = 'lobby'
        st.session_state.room_id = None
        st.rerun()
        
    # TODO: Implementasikan listener WebSocket di sini untuk otomatis
    # pindah ke halaman game saat pemain kedua bergabung.
    # Untuk saat ini, kita bisa menambahkan tombol manual.
    st.write("---")
    st.write("Jika pemain kedua sudah bergabung, klik tombol di bawah ini untuk memulai.")
    if st.button("Mulai Permainan!", type="primary"):
        st.session_state.page = 'game_room'
        st.rerun()

# =====================================================================
# BAGIAN Halaman 3: ARENA PERMAINAN
# =====================================================================
def render_game_room():
    st.header(f"Arena Pertandingan - Room: `{st.session_state.room_id}`")
    
    # Inisialisasi komponen video & deteksi tangan
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
                st.session_state['detected_gesture'] = gesture
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
        # Logika pengiriman gerakan via WebSocket
        # (Sama seperti sebelumnya, disederhanakan di sini)
        st.success(f"Gerakan '{st.session_state.detected_gesture}' terkirim!")
        # TODO: Implementasi WebSocket send & receive
        
    if st.session_state.game_result:
        # Tampilkan hasil permainan
        st.subheader("Hasil Ronde:")
        st.write(st.session_state.game_result)

    if st.button("Keluar dari Room"):
        st.session_state.page = 'lobby'
        st.session_state.room_id = None
        st.session_state.game_result = None
        st.rerun()

# =====================================================================
# Navigasi Utama Aplikasi
# =====================================================================
st.title("Gunting Batu Kertas Online 🏛️✂️📄")

if st.session_state.page == 'lobby':
    render_lobby()
elif st.session_state.page == 'waiting_room':
    render_waiting_room()
elif st.session_state.page == 'game_room':
    render_game_room()
