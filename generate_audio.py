import requests
import json
import os
import time

# 設定
BASE_URL = "http://localhost:50021"
OUTPUT_DIR = "audio"

# キャラクター設定
# SPEAKER_ID: 
# 3: ずんだもん (ノーマル)
# 2: 四国めたん (ノーマル)
# 8: 春日部つむぎ (ノーマル)
# 20: もち子さん (ノーマル)
# 23: WhiteCUL (通常)
# 24: WhiteCUL (たのしい)
# 47: ナースロボ＿タイプT (ノーマル)
# 29: No.7 (ノーマル)

CHARACTERS = {
    "zundamon": {"id": 3, "name": "ずんだもん"},
    "metan": {"id": 2, "name": "四国めたん"},
    "tsumugi": {"id": 8, "name": "春日部つむぎ"},
    "mochiko": {"id": 20, "name": "もち子さん"},
    "whitecul": {"id": 24, "name": "WhiteCUL"},
    "nurse_t": {"id": 47, "name": "ナースロボ＿タイプT"},
    "no7": {"id": 29, "name": "No.7"}
}

def generate_voice(text, filename, speaker_id, output_subdir, pitchScale=0, intonationScale=1):
    save_dir = os.path.join(OUTPUT_DIR, output_subdir)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 音声クエリの作成
    response = requests.post(
        f"{BASE_URL}/audio_query",
        params={"text": text, "speaker": speaker_id}
    )
    if response.status_code != 200:
        print(f"Error: audio_query failed for {text}")
        return False

    query_data = response.json()
    query_data["pitchScale"] = pitchScale
    query_data["intonationScale"] = intonationScale

    # 音声合成
    response = requests.post(
        f"{BASE_URL}/synthesis",
        params={"speaker": speaker_id},
        data=json.dumps(query_data)
    )
    if response.status_code != 200:
        print(f"Error: synthesis failed for {text}")
        return False

    # ファイル保存
    with open(os.path.join(save_dir, filename), "wb") as f:
        f.write(response.content)
    
    print(f"Generated: {output_subdir}/{filename} ({text})")
    return True

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for char_key, char_info in CHARACTERS.items():
        print(f"\n--- Generating voices for {char_info['name']} ---")
        speaker_id = char_info["id"]
        subdir = char_key

        # 1. 0分〜59分
        for i in range(60):
            text = f"{i}分をおしらせします。"
            if i == 0:
                text = "0分ちょうどをおしらせします。"
            filename = f"{i:02d}min.wav"
            if not os.path.exists(os.path.join(OUTPUT_DIR, subdir, filename)):
                generate_voice(text, filename, speaker_id, subdir)
                time.sleep(0.1)

        # 2. 0時〜23時
        for i in range(24):
            text = f"{i}時。"
            filename = f"{i:02d}hour.wav"
            if not os.path.exists(os.path.join(OUTPUT_DIR, subdir, filename)):
                generate_voice(text, filename, speaker_id, subdir)
                time.sleep(0.1)

        # 3. その他
        generate_voice("時報アプリを起動しました。", "startup.wav", speaker_id, subdir)
        generate_voice("読み上げテストです。", "test.wav", speaker_id, subdir)

    # カウントダウン用擬音（これは全キャラ共通でaudio直下に配置）
    print("\n--- Generating countdown sounds (common) ---")
    generate_voice("ピッ", "beep_short.wav", 3, ".", pitchScale=0.5)
    generate_voice("ポーン", "beep_long.wav", 3, ".")

if __name__ == "__main__":
    main()
