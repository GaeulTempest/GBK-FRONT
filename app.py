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
# Pastikan URL ini sudah benar sesuai dengan dashboard Railway Anda
BACKEND_URL_HTTP = "https://gbk-production.up.railway.app/"  # <-- GANTI SESUAI URL ANDA
BACKEND_URL_WS = "wss://gbk-production.up.railway.app/ws"    # <-- GANTI SESUAI URL ANDA

# Inisialisasi detector tangan dari CVZone
detector = HandDetector(staticMode=False, maxHands=1, detectionCon=0.8, minTrackCon=0.5)

# Konfigurasi STUN server untuk WebRTC
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# --- Fungsi Helper ---
def classify_gesture(fingers: list) -> str:
    if fingers == [0, 0, 0, 0, 0]: return "rock"
    if fingers == [1, 1, 1, 1, 1]: return "paper"
    if fingers == [0, 1, 1, 0, 0]: return "scissors"
    return "none"

# --- Callback untuk Memproses Frame Video ---
class VideoProcessor:
    def __init__(self):
        self.last_gesture = "none"
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        hands, img_processed = detector.findHands(img)
        if hands:
            hand = hands[0]
            fingers = detector.fingersUp(hand)
            gesture = classify_gesture(fingers)
            if gesture != "none":
                st.session_state['detected_gesture'] = gesture
                self.last_gesture = gesture
            cv2.putText(img_processed, self.last_gesture, (hand['bbox'][0], hand['bbox'][1] - 20), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
        return av.VideoFrame.from_ndarray(img_processed, format="bgr24")

# --- UI Aplikasi Streamlit ---
st.set_page_config(page_title="Gunting Batu Kertas Online", layout="centered")
st.title("🎮 Gunting Batu Kertas Online")

if 'player_id' not in st.session_state: st.session_state['player_id'] = str(uuid.uuid4())
if 'room_id' not in st.session_state: st.session_state['room_id'] = None
# ... (inisialisasi state lainnya)

if not st.session_state['room_id']:
    st.header("Lobby Permainan")
    if st.button("Buat Room Baru", use_container_width=True):
        try:
            # ==========================================================
            # TAMBAHAN: Tampilkan URL yang akan diakses untuk debugging
            # ==========================================================
            target_url = f"{BACKEND_URL_HTTP}/create_room"
            st.info(f"Mencoba mengakses: {target_url}")
            # ==========================================================
            
            response = requests.post(target_url)
            if response.status_code == 200:
                room_id = response.json()['room_id']
                st.session_state['room_id'] = room_id
                st.rerun()
            else:
                st.error(f"Gagal membuat room. Status: {response.status_code}")
                st.error(f"Response Body: {response.text}") # Tampilkan juga body response
        except requests.exceptions.RequestException as e:
            st.error("Gagal membuat room. Server mungkin tidak aktif atau URL salah.")
            st.error(f"Detail: {e}")
    
    join_room_id = st.text_input("Masukkan Room ID untuk Bergabung", key="join_id")
    if st.button("Gabung Room", use_container_width=True):
        if join_room_id:
            st.session_state['room_id'] = join_room_id
            st.rerun()
# ... (sisa kode UI permainan)
