# 🤖 My Arduino LLM Project

> Arduino와 대형 언어 모델(LLM)을 연동한 임베디드 AI 프로젝트

[![C++](https://img.shields.io/badge/C++-84.6%25-00599C?style=flat-square&logo=c%2B%2B)](https://isocpp.org/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python)](https://python.org)
[![Arduino](https://img.shields.io/badge/Arduino-Compatible-00979D?style=flat-square&logo=arduino)](https://arduino.cc)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## 📌 프로젝트 소개

Arduino 마이크로컨트롤러와 PC에서 실행되는 LLM(대형 언어 모델)을 시리얼 통신으로 연결하여, 실제 하드웨어가 AI의 응답에 따라 동작하는 시스템입니다.

<!-- ✏️ TODO: 프로젝트의 구체적인 목적이나 배경을 한 줄로 추가해 주세요 -->

---

## 🎬 시연 영상
https://github.com/jamongadejoa28/my-arduino-llm-project/issues/2#issue-3967127088
https://github.com/jamongadejoa28/my-arduino-llm-project/issues/2#issuecomment-3932256777

---

## 🗂️ 프로젝트 구조

```
my-arduino-llm-project/
├── firmware/          # Arduino 펌웨어 (C++)
│   └── ...            # 센서 데이터 수집 및 시리얼 통신 코드
├── pc_app/            # PC 앱 (Python)
│   └── ...            # LLM API 연동 및 시리얼 통신 처리
├── requirements.txt   # Python 의존성 패키지
└── README.md
```

---

## ✨ 주요 기능

- **실시간 시리얼 통신**: Arduino ↔ PC 간 양방향 데이터 송수신
- **LLM 연동**: PC에서 LLM API를 호출하여 AI 응답 생성
- **하드웨어 제어**: LLM의 응답을 기반으로 Arduino 하드웨어 동작 제어
<!-- ✏️ TODO: 실제 기능(센서 종류, LED/모터 제어 등)에 맞게 수정해 주세요 -->

---

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| 펌웨어 | C++, Arduino IDE |
| PC 앱 | Python 3.x, Jupyter Notebook |
| 빌드 시스템 | CMake |
| AI | LLM API (OpenAI / Ollama 등) |
| 통신 | Serial (UART) |

<!-- ✏️ TODO: 실제 사용한 LLM(OpenAI GPT, Llama, Gemini 등)을 명시해 주세요 -->

---

## ⚙️ 설치 및 실행

### 요구 사항

- Arduino 보드 (Uno / Mega / 등)
- Python 3.8 이상
- Arduino IDE
- LLM API 키 (또는 로컬 LLM 환경)

### 1. 레포지토리 클론

```bash
git clone https://github.com/jamongadejoa28/my-arduino-llm-project.git
cd my-arduino-llm-project
```

### 2. Python 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. Arduino 펌웨어 업로드

1. `firmware/` 폴더의 `.ino` 파일을 Arduino IDE에서 열기
2. 보드와 포트 선택 후 업로드

### 4. PC 앱 실행

```bash
cd pc_app
python main.py
```

<!-- ✏️ TODO: 실제 실행 파일명, API 키 설정 방법 등을 추가해 주세요 -->

---

## 🔌 하드웨어 연결

<!-- ✏️ TODO: 회로 연결도 또는 핀 배치표를 추가해 주세요 -->

| Arduino 핀 | 연결 부품 |
|------------|---------|
| D9 | ... |
| A0 | ... |
| GND | GND |

---

## 📸 스크린샷

<!-- ✏️ TODO: 스크린샷 이미지를 추가해 주세요 -->
<!-- ![screenshot](./assets/screenshot.png) -->
