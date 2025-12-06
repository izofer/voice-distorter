import os
from pydub import AudioSegment, effects
from pydub.generators import Sine
import numpy as np
import scipy.signal

# Configure Pydub to use local FFmpeg binaries if available (Windows Dev Check)
# This overrides the system PATH check which can be flaky on Windows
bin_path = os.path.join(os.getcwd(), 'bin')
local_ffmpeg = os.path.join(bin_path, 'ffmpeg.exe')
local_ffprobe = os.path.join(bin_path, 'ffprobe.exe')

if os.path.exists(local_ffmpeg) and os.path.exists(local_ffprobe):
    # LOCAL WINDOWS DEV ENVIRONMENT
    os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
    AudioSegment.converter = local_ffmpeg
    AudioSegment.ffprobe = local_ffprobe
    print(f"DEBUG: Using local FFmpeg: {local_ffmpeg}")
else:
    # DOCKER / SYSTEM ENVIRONMENT
    # Pydub automatically finds 'ffmpeg' in system PATH
    # We do NOT set AudioSegment.converter explicitly, letting shutil.which find it
    print("DEBUG: Using system FFmpeg (Docker/Global)")

# Check if pydub can actually find ffmpeg (for debugging logs)
from pydub.utils import which
if which("ffmpeg"):
    print(f"DEBUG: FFmpeg found at: {which('ffmpeg')}")
else:
    print("CRITICAL WARNING: FFmpeg not found in PATH!")

class AudioProcessor:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        self.effects_map = {
            'Reverse': lambda a, **k: a.reverse(),
            'Monster': lambda a, **k: self.change_pitch(a, 0.6),
            'Child': lambda a, **k: self.change_pitch(a, 1.4),
            'Fast': lambda a, **k: self.change_speed(a, 1.5),
            'Old Man': lambda a, **k: self.tremolo(self.change_pitch(a, 0.85), 100), # Lower pitch, shakiness
            'Woman': lambda a, **k: self.change_pitch(a, 1.3),
            'Ghost': lambda a, **k: self.apply_ethereal(a),
            'Tibetan Monk': lambda a, **k: self.apply_echo(self.change_pitch(a, 0.5), delay_ms=800, decay=0.8).low_pass_filter(800), # Deep, resonant, muffled
            'Vibrato': lambda a, **k: self.vibrato(a),
            'Tremolo': lambda a, **k: self.tremolo(a),
            'Custom': lambda a, **k: self.apply_custom(a, **k)
        }

    def get_effects_list(self):
        # Exclude 'Custom' from the default list if we want to treat it special in UI,
        # but user wants it as an option. We will return it, or handle it in UI.
        # Let's return all.
        return list(self.effects_map.keys())

    def load_audio(self, filename):
        path = os.path.join(self.upload_folder, filename)
        return AudioSegment.from_file(path)

    def save_audio(self, audio, filename):
        path = os.path.join(self.upload_folder, filename)
        audio.export(path, format="mp3")
        return path

    def apply_effect(self, audio, effect_type, params=None):
        if params is None: params = {}
        
        if isinstance(effect_type, list):
            for effect in effect_type:
                audio = self.apply_single_effect(audio, effect, params)
            return audio
        return self.apply_single_effect(audio, effect_type, params)

    def apply_single_effect(self, audio, effect_name, params=None):
        if params is None: params = {}
        
        # Exact match
        if effect_name in self.effects_map:
            return self.effects_map[effect_name](audio, **params)
        
        # Case insensitive match
        for key in self.effects_map:
            if key.lower() == str(effect_name).lower():
                 return self.effects_map[key](audio, **params)
                 
        return audio
        
    def apply_custom(self, audio, pitch=1.0, speed=1.0, distortion=0, **kwargs):
        # Apply custom params
        pitch = float(pitch)
        speed = float(speed)
        distortion = float(distortion)
        
        if pitch != 1.0:
            audio = self.change_pitch(audio, pitch)
        if speed != 1.0:
            audio = self.change_speed(audio, speed)
        if distortion > 0:
            audio = self.apply_distortion(audio, gain=distortion)
        return audio
    
    # --- EFFECT IMPLEMENTATIONS ---

    def change_speed(self, audio, speed=1.0):
        new_frame_rate = int(audio.frame_rate * speed)
        return audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate}).set_frame_rate(audio.frame_rate)
        
    def change_pitch(self, audio, octaves):
        new_sample_rate = int(audio.frame_rate * octaves)
        chunk = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
        return chunk.set_frame_rate(audio.frame_rate)

    def apply_echo(self, audio, delay_ms=500, decay=0.6):
        output_audio = audio
        for i in range(1, 4):
            delay = delay_ms * i
            if delay > len(audio): break
            volume = decay ** i
            silence = AudioSegment.silent(duration=delay)
            delayed = silence + audio
            delayed = delayed - (10 * i)
            output_audio = output_audio.overlay(delayed)
        return output_audio

    def modulate(self, audio, freq):
        sine_wave = Sine(freq).to_audio_segment(duration=len(audio))
        return audio.overlay(sine_wave - 10)

    def apply_distortion(self, audio, gain=15):
        return (audio + gain).normalize()

    def apply_ethereal(self, audio):
        reversed_audio = audio.reverse()
        with_echo = self.apply_echo(reversed_audio, delay_ms=800, decay=0.8)
        return with_echo.reverse()

    def wobble(self, audio):
        return audio.overlay(self.change_speed(audio, 1.05))

    def glitch(self, audio):
        chunks = []
        step = 100
        for i in range(0, len(audio), step):
            chunk = audio[i:i+step]
            if i % 200 == 0:
                chunks.append(chunk * 2) 
            else:
                chunks.append(chunk)
        return sum(chunks)

    def bitcrush(self, audio):
        return audio.set_frame_rate(8000).set_frame_rate(audio.frame_rate)

    def drone(self, audio):
        hum = Sine(60).to_audio_segment(duration=len(audio)) - 5
        return audio.overlay(hum)

    def poltergeist(self, audio):
        return self.glitch(self.change_pitch(audio.reverse(), 0.8))

    def zombie(self, audio):
        return self.change_speed(self.change_pitch(audio, 0.7), 0.8)

    def possessed(self, audio):
        low = self.change_pitch(audio, 0.5)
        return audio.overlay(low)

    def whisper(self, audio):
        return audio.high_pass_filter(1500) - 5

    def reverb(self, audio, room_size='large'):
        delay = 200 if room_size == 'large' else 50
        decay = 0.5
        return self.apply_echo(audio, delay_ms=delay, decay=decay)

    def radio(self, audio):
        return audio.high_pass_filter(500).low_pass_filter(3000).overlay(Sine(10000).to_audio_segment(duration=len(audio)) - 30)

    def vader(self, audio):
        deep = self.change_pitch(audio, 0.75)
        return deep.low_pass_filter(2000)

    def add_static(self, audio):
        return audio.overlay(Sine(15000).to_audio_segment(duration=len(audio)) - 20)

    def tremolo(self, audio, chunk_size=50):
        # Start/Stop rapid volume change
        chunks = []
        step = chunk_size 
        for i in range(0, len(audio), step):
            chunk = audio[i:i+step]
            if (i // step) % 2 == 0:
                chunks.append(chunk)
            else:
                chunks.append(chunk - 10)
        return sum(chunks)


    def vibrato(self, audio):
        # Pitch wobble?
        return audio.overlay(self.change_speed(audio, 1.02))

    def chorus(self, audio):
        return audio.overlay(self.change_pitch(audio, 1.01)).overlay(self.change_pitch(audio, 0.99))
