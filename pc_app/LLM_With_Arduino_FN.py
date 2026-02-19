#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import time
import re
import serial
import requests
import os
import random
from dataclasses import dataclass, asdict
from typing import Optional, Final
from threading import Thread, Lock

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6 import uic
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer

# =========================
# Configuration
# =========================
# [UPDATE] 사용자 피드백 반영: 성능이 더 좋은 gemma3:4b 모델 사용
OLLAMA_HOST: Final = "http://127.0.0.1:11434"
OLLAMA_URL: Final = f"{OLLAMA_HOST}/api/chat"
MODEL_NAME: Final = "gemma3:4b"  
SERIAL_PORT: Final = "/dev/ttyACM0" 
BAUD_RATE: Final = 115200
PROMPT_FILE: Final = "system_prompt.txt"

ANGER_KEYWORDS = ['빡쳐', '짜증', '성질', '꺼져', '닥쳐', '씨발', '개빡', '화나', '죽을']

BUTTON_MESSAGES = [
    "안녕?", "와썹!", "오늘 기분 어때?", 
    "심심해 놀아줘", "너는 누구야?", "사랑해", 
    "노래 한 소절 불러줘", "무서운 이야기 해줘", 
    "독도는 누구 땅?", "2 더하기 2는?"
]

# ASCII Emoticons for Random Injection
EMOTICONS = {
    "happy": ["^_^", "^o^", "<3", ":)", "B-)", ":D", "XD"],
    "sad": ["T_T", "(ToT)", ";_;", "T.T", "..", ">_<"],
    "angry": ["-^-", ">_<", "-_-", "!!!!", "Orz"],
    "neutral": ["OoO", "OwO", "Hmm", ":]", "?_?", "(?)"]
}

# =========================
# Data Structures
# =========================
@dataclass
class SensorData:
    temp: float = 0.0
    humid: float = 0.0
    light: int = 0
    btn: int = 0
    timestamp: float = 0.0
    
    @property
    def discomfort_index(self) -> float:
        try:
            rh_decimal = self.humid / 100.0
            di = (1.8 * self.temp) - (0.55 * (1 - rh_decimal) * (1.8 * self.temp - 26)) + 32
            return round(di, 1)
        except Exception:
            return 0.0

    @property
    def weather_status(self) -> str:
        di = self.discomfort_index
        if di < 68: return "Pleasant"
        elif 68 <= di < 75: return "Moderate"
        elif 75 <= di < 80: return "Uncomfortable"
        else: return "Dangerous"

    @property
    def light_status(self) -> str:
        if self.light >= 600: return "Dark"
        elif self.light <= 150: return "Bright"
        else: return "Normal"

@dataclass(frozen=True)
class RobotCommand:
    seq: int
    l1: str
    l2: str
    chat_response: str
    mood: str 
    act: str 

    def to_json_serial(self) -> str:
        data = {
            "seq": self.seq,
            "l1": self.l1,
            "l2": self.l2,
            "mood": self.mood,
            "act": self.act
        }
        return json.dumps(data) + "\n"

# =========================
# Hardware Controller
# =========================
class SmartController(QObject):
    sensor_received = pyqtSignal(SensorData)

    def __init__(self, port: str, baud: int):
        super().__init__()
        self.serial: Optional[serial.Serial] = None
        self.port = port
        self.baud = baud
        self._connect_serial()
        
        self._seq_counter: int = 0
        self.is_running: bool = True
        self.lock = Lock()
        self.current_sensor = SensorData()
        
        if self.serial:
            self.receiver_thread = Thread(target=self._listen_serial, daemon=True)
            self.receiver_thread.start()

    def _connect_serial(self):
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=0.1)
            print(f"✅ 시리얼 포트 연결 성공: {self.port}")
            time.sleep(2) 
        except Exception as e:
            print(f"⚠️ 시리얼 연결 실패 (시뮬레이션): {e}")

    def _listen_serial(self) -> None:
        while self.is_running and self.serial and self.serial.is_open:
            try:
                if self.serial.in_waiting > 0:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if not line: continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "SENSOR":
                            with self.lock:
                                self.current_sensor = SensorData(
                                    temp=float(data.get("temp", 0)),
                                    humid=float(data.get("humid", 0)),
                                    light=int(data.get("light", 0)),
                                    btn=int(data.get("btn", 0)),
                                    timestamp=time.time()
                                )
                            self.sensor_received.emit(self.current_sensor)
                    except json.JSONDecodeError:
                        pass 
            except Exception as e:
                time.sleep(1)

    def send_command(self, cmd: RobotCommand) -> None:
        if self.serial and self.serial.is_open:
            try:
                payload = cmd.to_json_serial().encode('utf-8')
                self.serial.write(payload)
            except Exception as e:
                print(f"[Serial Error] 전송 실패: {e}")

    def get_next_seq(self) -> int:
        self._seq_counter += 1
        return self._seq_counter
        
    def get_sensor_data(self) -> SensorData:
        with self.lock:
            return self.current_sensor

    def close(self) -> None:
        self.is_running = False
        if self.serial and self.serial.is_open:
            self.serial.close()

# =========================
# LLM Worker
# =========================
class LLMWorker(QThread):
    result_signal = pyqtSignal(RobotCommand)
    error_signal = pyqtSignal(str)

    def __init__(self, query: str, seq: int, sensor_data: SensorData):
        super().__init__()
        self.query = query
        self.seq = seq
        self.sensor_data = sensor_data
        
    def _construct_system_prompt(self) -> str:
        base_prompt = ""
        try:
            base_path = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(base_path, PROMPT_FILE)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    base_prompt = f.read()
            else:
                base_prompt = "You are Artie. JSON Output required."
        except Exception:
            base_prompt = "You are Artie. JSON Output required."
            
        prompt = base_prompt.replace("{temp}", str(self.sensor_data.temp))
        prompt = prompt.replace("{humid}", str(self.sensor_data.humid))
        prompt = prompt.replace("{light}", str(self.sensor_data.light))
        prompt = prompt.replace("{light_status}", self.sensor_data.light_status)
        
        # [UPDATE] 시스템 알림을 조금 더 부드럽게 변경
        if self.sensor_data.light_status == "Dark":
            prompt += "\n[ENV INFO] Dark environment. Act sleepy or scared."
        elif self.sensor_data.light_status == "Bright":
            prompt += "\n[ENV INFO] Bright environment. Act energetic."
            
        return prompt

    def run(self):
        is_furious = any(k in self.query for k in ANGER_KEYWORDS)
        
        system_prompt = self._construct_system_prompt()
        
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.query}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.6, # 창의성 약간 증가
                "top_p": 0.9
            }
        }

        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=25)
            response.raise_for_status()
            
            data = response.json()
            content = data["message"]["content"]
            
            parsed = {}
            try:
                # JSON 추출 로직 (Markdown 코드블록 대응)
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx : end_idx + 1]
                    parsed = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", content, 0)
                    
            except json.JSONDecodeError:
                parsed = {
                    "l1": "Thinking...", 
                    "l2": "Wait a sec >_<", 
                    "chat": "음... 무슨 말인지 곰곰이 생각 중이에요.", 
                    "mood": "neutral", 
                    "act": "scan"
                }

            l1 = str(parsed.get("l1", "")).strip()
            l2 = str(parsed.get("l2", "")).strip()
            mood = str(parsed.get("mood", "neutral"))
            act = str(parsed.get("act", "none"))
            chat = str(parsed.get("chat", ""))

            # 빈 응답 방어
            if not l1 and not chat:
                l1 = "Unknown..."
                l2 = "?_?"
                chat = "다시 한 번 말씀해 주시겠어요?"
                act = "scan"

            # 1. 분노 필터 (강제)
            if is_furious:
                mood = "angry"
                act = "shake"
                l1 = "-^-"
                l2 = "Sorry..."
                if "죄송" not in chat and "미안" not in chat:
                    chat = "히익! 제가 잘못했어요... 용서해주세요 ㅠㅠ"

            # 2. 감정-행동 보정
            if mood == "sad" and act == "nod": act = "none"
            elif mood == "angry" and act == "nod": act = "shake"

            # 3. LCD 정제 및 이모티콘 강화
            def clean_and_enrich_lcd(text, mood, is_line2=False):
                # ASCII만 남기기
                cleaned = "".join([c for c in text if ord(c) < 128]).strip()
                
                # 내용이 없으면 기본값
                if not cleaned:
                    if is_line2: cleaned = "..." 
                    else: cleaned = "Artie Robot"

                # 너무 길면 자르기 (이모티콘 공간 확보를 위해 13자 정도)
                if len(cleaned) > 13:
                    cleaned = cleaned[:13]
                
                # 랜덤 이모티콘 추가 (이미 특수문자가 많지 않다면)
                # 라인 2에 더 적극적으로 넣음
                chance = 0.7 if is_line2 else 0.3
                if len(cleaned) < 13 and random.random() < chance:
                    if not re.search(r'[\^<>]', cleaned): 
                        emo_list = EMOTICONS.get(mood, EMOTICONS["neutral"])
                        emoji = random.choice(emo_list)
                        cleaned = f"{cleaned} {emoji}"
                
                return cleaned

            l1 = clean_and_enrich_lcd(l1, mood, is_line2=False)
            l2 = clean_and_enrich_lcd(l2, mood, is_line2=True)

            cmd = RobotCommand(
                seq=self.seq,
                l1=l1[:16],
                l2=l2[:16],
                chat_response=chat,
                mood=mood,
                act=act
            )
            self.result_signal.emit(cmd)

        except requests.exceptions.RequestException as e:
            # "[CRITICAL]" 태그를 붙여서 GUI에 보냄
            self.error_signal.emit(f"[CRITICAL] API Connection Failed: {e}")

        except Exception as e:
            # 일반적인 파이썬 에러
            self.error_signal.emit(f"LLM Error: {str(e)}")

# =========================
# GUI
# =========================
try:
    from_class = uic.loadUiType("LLM_With_Arduino.ui")[0]
except FileNotFoundError:
    from_class = QMainWindow

class LlmGui(QMainWindow, from_class):
    def __init__(self):
        super().__init__()
        try: self.setupUi(self)
        except AttributeError: self._init_ui_manually()

        self.setWindowTitle("Arduino Pet Robot - Artie (Gemma Mode)")
        self.hw = SmartController(SERIAL_PORT, BAUD_RATE)
        self.hw.sensor_received.connect(self.update_sensor_ui)
        
        self.inputButton.clicked.connect(self.process_input)
        self.inputLine.returnPressed.connect(self.process_input)
        
        self.is_closing_sequence = False
        
        self.last_light_status = "Normal"
        self.last_auto_trigger_time = 0
        self.prev_btn_state = 0
        
        self.append_system_msg("시스템 시작. Gemma 두뇌 탑재 완료.")

    def _init_ui_manually(self):
        self.resize(600, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.lcdDisplay = QLabel("Initializing...", self)
        self.lcdDisplay.setStyleSheet("background-color: #99FF66; border: 2px solid #555; font-family: monospace; font-size: 20px; padding: 10px;")
        self.lcdDisplay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lcdDisplay)

        self.sensorLabel = QLabel("Waiting Sensor...", self)
        self.sensorLabel.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        layout.addWidget(self.sensorLabel)

        self.responseBox = QTextBrowser(self)
        layout.addWidget(self.responseBox)

        inp_layout = QHBoxLayout()
        self.inputLine = QLineEdit(self)
        self.inputButton = QPushButton("Send", self)
        inp_layout.addWidget(self.inputLine)
        inp_layout.addWidget(self.inputButton)
        layout.addLayout(inp_layout)

    def update_sensor_ui(self, data: SensorData):
        status_text = f"Temp: {data.temp}°C  |  Humid: {data.humid}%  |  Light: {data.light} ({data.light_status})"
        self.sensorLabel.setText(status_text)
        
        # 1. 조도 변화 자동 감지
        current_light = data.light_status
        now = time.time()
        
        if (current_light != self.last_light_status) and \
           (now - self.last_auto_trigger_time > 5.0) and \
           (not self.is_closing_sequence):
            
            if current_light in ["Dark", "Bright"]:
                print(f"⚡ [Auto-Trigger] Light changed to {current_light}")
                self.last_auto_trigger_time = now
                self.trigger_auto_reaction(current_light)
            
            self.last_light_status = current_light
            
        # 2. 버튼 입력 처리
        if data.btn == 1 and self.prev_btn_state == 0 and not self.is_closing_sequence:
            random_msg = random.choice(BUTTON_MESSAGES)
            self.lcdDisplay.setText(f"Btn: {random_msg[:11]}..")
            self.inputLine.setText(random_msg)
            self.process_input()
        
        self.prev_btn_state = data.btn

    def trigger_auto_reaction(self, light_status):
        msg = f"[환경 변화 감지] 조명 상태가 '{light_status}'로 변경되었습니다."
        self.append_system_msg(msg)
        
        query_text = f"(System Alert: The light level just changed to {light_status}. React to this sudden change immediately!)"
        
        self.lcdDisplay.setText("Sensing...")
        
        current_sensors = self.hw.get_sensor_data()
        self.worker = LLMWorker(query_text, self.hw.get_next_seq(), current_sensors)
        self.worker.result_signal.connect(self.on_llm_finish)
        self.worker.error_signal.connect(self.on_llm_error)
        self.worker.start()

    def process_input(self):
        if self.is_closing_sequence: return 

        raw_text = self.inputLine.text().strip()
        if not raw_text: return

        closing_keywords = ['quit', 'exit', '종료']
        is_shutdown_cmd = raw_text.lower() in closing_keywords
        
        query_text = raw_text
        
        if is_shutdown_cmd:
            print("🛑 프로그램 종료 요청됨. 작별 인사를 시작합니다.")
            self.is_closing_sequence = True
            query_text = "System Termination"
            self.inputLine.setEnabled(False)
            self.inputButton.setEnabled(False)
        
        self.append_chat_msg("Me", raw_text, True)
        print(f"🗣️ [Me] {raw_text}")
        
        self.inputLine.clear()
        if not is_shutdown_cmd:
            self.inputLine.setEnabled(False)
            
        if "Btn:" not in self.lcdDisplay.text():
             self.lcdDisplay.setText("Thinking...")
        
        current_sensors = self.hw.get_sensor_data()
        self.worker = LLMWorker(query_text, self.hw.get_next_seq(), current_sensors)
        self.worker.result_signal.connect(self.on_llm_finish)
        self.worker.error_signal.connect(self.on_llm_error)
        self.worker.start()

    def on_llm_finish(self, cmd: RobotCommand):
        self.hw.send_command(cmd)
        
        self.lcdDisplay.setText(f"{cmd.l1}\n{cmd.l2}")
        self.append_chat_msg("Artie", cmd.chat_response, False)
        
        print(f"🤖 [Artie] {cmd.chat_response}")
        print(f"   ↪ LCD: [{cmd.l1}] / [{cmd.l2}] | Mood: {cmd.mood} | Act: {cmd.act}")
        
        if self.is_closing_sequence:
            self.append_system_msg("3초 후 시스템이 종료됩니다...")
            QTimer.singleShot(3000, self.close)
        else:
            self.inputLine.setEnabled(True)
            self.inputLine.setFocus()

    def on_llm_error(self, err: str):
        # 시스템 메시지 출력
        self.append_system_msg(f"Error: {err}")
        print(f"⚠️ [Error] {err}")
        
        # [변경] 치명적인 API 오류(400, 연결실패 등) 감지 시 종료 처리
        if "[CRITICAL]" in err or "400" in err:
            self.append_system_msg("⛔ 치명적인 서버 오류가 발생했습니다.")
            self.append_system_msg("3초 후 프로그램을 자동 종료합니다...")
            
            # 입력 차단
            self.inputLine.setEnabled(False)
            self.inputButton.setEnabled(False)
            self.is_closing_sequence = True
            
            # 3초 후 종료 (사용자가 에러 메시지를 읽을 시간 확보)
            QTimer.singleShot(3000, self.close)
            return

        # 일반 에러인 경우 기존 로직 수행
        if self.is_closing_sequence:
            QTimer.singleShot(2000, self.close)
        else:
            self.inputLine.setEnabled(True)

    def append_chat_msg(self, sender, text, is_user):
        align = "right" if is_user else "left"
        color = "#e6f2ff" if is_user else "#ffffff"
        self.responseBox.append(f"<div style='text-align:{align};'><span style='background:{color};padding:5px;'><b>{sender}</b>: {text}</span></div>")

    def append_system_msg(self, text):
        self.responseBox.append(f"<div style='text-align:center;color:gray;font-size:small;'>{text}</div>")

    def closeEvent(self, event):
        self.hw.close()
        print("✅ 시스템이 안전하게 종료되었습니다.")
        event.accept()

def main():
    app = QApplication(sys.argv)
    win = LlmGui()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()