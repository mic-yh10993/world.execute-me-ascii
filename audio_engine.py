"""Cross-platform audio engine for the world.execute(me); terminal MV player.

Implements exactly the same line protocol as AudioClock.swift (macOS):

  stdin commands (one per line):
      play | pause | seek <seconds> | volume <0..1> | quit
  stdout: one JSON object per line, ~60 Hz:
      {"time": <seconds>, "duration": <seconds>, "playing": <bool>}
      or {"error": "<message>"} on fatal failure

Playback itself is done with just_playback (miniaudio, prebuilt wheels),
whose play() always restarts from 0 and whose seek() only works while the
stream is active. This engine keeps a small state machine so the command
semantics match AVAudioPlayer: 'play' means "keep position, ensure
playing", and a 'seek' issued while idle is remembered and applied on the
next 'play'.
"""
import json
import sys
import threading
import time


def run_engine(audio_path):
    try:
        from just_playback import Playback
    except Exception as e:  # pragma: no cover
        sys.stdout.write(json.dumps({'error': 'audio backend missing: %s' % e}) + '\n')
        sys.stdout.flush()
        return 1
    try:
        pb = Playback()
        pb.load_file(str(audio_path))
    except Exception as e:
        sys.stdout.write(json.dumps({'error': str(e)}) + '\n')
        sys.stdout.flush()
        return 1
    pb.set_volume(0.75)
    duration = pb.duration or 0.0

    lock = threading.Lock()
    pending_seek = None
    quitting = False

    def set_pending(value):
        nonlocal pending_seek
        with lock:
            pending_seek = value

    def take_pending():
        nonlocal pending_seek
        with lock:
            value, pending_seek = pending_seek, None
            return value

    def cmd_play():
        pending = take_pending()
        try:
            if pb.paused:
                pb.resume()
            elif not pb.playing:
                pb.play()  # just_playback always restarts from 0 ...
            if pending is not None and pb.active:
                pb.seek(pending)  # ... so re-apply the wanted position
        except Exception:
            pass

    def cmd_pause():
        try:
            pb.pause()
        except Exception:
            pass

    def cmd_seek(raw):
        try:
            t = min(max(0.0, float(raw)), max(0.0, duration - 0.01))
        except ValueError:
            return
        try:
            if pb.active:
                pb.seek(t)
            else:
                set_pending(t)
        except Exception:
            pass

    def cmd_volume(raw):
        try:
            pb.set_volume(min(1.0, max(0.0, float(raw))))
        except (ValueError, Exception):
            pass

    def reader():
        nonlocal quitting
        for line in sys.stdin:
            parts = line.strip().split(' ', 1)
            cmd = parts[0]
            arg = parts[1] if len(parts) > 1 else ''
            if cmd == 'play':
                cmd_play()
            elif cmd == 'pause':
                cmd_pause()
            elif cmd == 'seek':
                cmd_seek(arg)
            elif cmd == 'volume':
                cmd_volume(arg)
            elif cmd == 'quit':
                break
        quitting = True

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        while not quitting:
            try:
                pos = pb.curr_pos
                if pos is None or pos < 0:
                    pos = 0.0
                sys.stdout.write(json.dumps(
                    {'time': pos, 'duration': duration,
                     'playing': bool(pb.playing)}) + '\n')
                sys.stdout.flush()
            except Exception:
                break
            time.sleep(1.0 / 60.0)
    finally:
        quitting = True
        try:
            pb.close()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(run_engine(sys.argv[1]))
