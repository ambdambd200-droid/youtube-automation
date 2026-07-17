import subprocess, json

fp = r'C:\Users\A\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe'
f = r'C:\Users\A\Desktop\Movies\assets\clips\movie_79ad794b00.mp4'

r = subprocess.run([fp, '-v', 'quiet', '-print_format', 'json', '-show_streams', f], capture_output=True, text=True, timeout=15)
if r.returncode:
    print('ffprobe error:', r.stderr[:200])
else:
    d = json.loads(r.stdout)
    for s in d['streams']:
        t = s['codec_type']
        if t == 'video':
            print(f'Video: {s["width"]}x{s["height"]} @ {s["r_frame_rate"]}fps, codec={s["codec_name"]}')
        if t == 'audio':
            print(f'Audio: codec={s["codec_name"]}, sr={s.get("sample_rate","?")}Hz, ch={s.get("channels","?")}')
    print(f'File size: {__import__("os").path.getsize(f) / 1024 / 1024:.1f} MB')
