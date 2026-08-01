import sys
import os
import wave
import numpy as np
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.stt_engine import STTEngine

def run_test():
    wav_path = "test_audio_full.wav"
    if not os.path.exists(wav_path):
        print(f"Error: {wav_path} not found. Please wait for yt-dlp to finish.")
        return

    print(f"Loading STT Engine (tiny.en)...")
    stt_engine = STTEngine("tiny.en")
    while not stt_engine._is_loaded:
        time.sleep(0.5)
    print("STT Engine loaded!")
    
    with wave.open(wav_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        print(f"Audio properties: {sample_rate}Hz, {channels} channels, {sampwidth} bytes/sample")
        
        # Skip to 263 seconds
        start_time_sec = 263.0
        end_time_sec = 293.0
        start_frame = int(start_time_sec * sample_rate)
        wf.setpos(start_frame)
        
        # AudioCapturer logic variables
        chunk_frames = 1024
        threshold = 350
        
        audio_buffer = bytearray()
        silence_counter = 0
        speaking = False
        
        total_frames_read = start_frame
        last_stream1c_len = 0
        
        print(f"\n--- STARTING SIMULATION AT {start_time_sec}s ---")
        
        while True:
            data = wf.readframes(chunk_frames)
            if not data:
                break
                
            total_frames_read += chunk_frames
            current_time_sec = total_frames_read / sample_rate
            
            if current_time_sec > end_time_sec:
                break
            
            # Simulated Energy VAD check
            audio_np = np.frombuffer(data, dtype=np.int16)
            # If stereo, average to mono for energy check
            if channels == 2:
                audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)
                
            energy = float(np.abs(audio_np).mean()) if len(audio_np) > 0 else 0.0
            
            if energy > threshold:
                audio_buffer.extend(data)
                speaking = True
                silence_counter = 0
                
                # Stream 1c trigger simulation
                # Trigger every ~150ms of new audio (approx 150ms * sample_rate * channels * sampwidth)
                bytes_per_150ms = int(0.15 * sample_rate * channels * sampwidth)
                if len(audio_buffer) - last_stream1c_len >= bytes_per_150ms:
                    partial_text = stt_engine.transcribe_audio_pcm(bytes(audio_buffer), sample_rate=sample_rate)
                    print(f"[{current_time_sec:.2f}s] [Stream 1c]: '{partial_text}'")
                    last_stream1c_len = len(audio_buffer)
                    
            else:
                if speaking:
                    silence_counter += 1
                    audio_buffer.extend(data)
                    
                    if silence_counter > 5:
                        # End of phrase (Stream 1a)
                        final_text = stt_engine.transcribe_audio_pcm(bytes(audio_buffer), sample_rate=sample_rate)
                        print(f"[{current_time_sec:.2f}s] [Stream 1a] (Phrase End): '{final_text}'")
                        print("-" * 50)

                        
                        audio_buffer = bytearray()
                        speaking = False
                        silence_counter = 0
                        last_stream1c_len = 0

if __name__ == "__main__":
    run_test()
