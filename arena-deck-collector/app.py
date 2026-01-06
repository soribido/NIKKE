import os
from flask import Flask, render_template, request, jsonify
import pyautogui
from PIL import Image, ImageDraw
import io, base64, threading
import tkinter as tk
from tkinter import filedialog

app = Flask(__name__)

region_by_id       = {}
region_user_by_id  = {}
deck_images        = {}
user_images        = {}
loss_flags         = [False]*10

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/screenshot')
def screenshot():
    img = pyautogui.screenshot()
    buf = io.BytesIO(); img.save(buf,'PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'image':'data:image/png;base64,' + b64})

@app.route('/set_region', methods=['POST'])
def set_region():
    data = request.get_json()
    did = int(data['deckId'])
    x,y,w,h = data['x'],data['y'],data['w'],data['h']
    # 항상 모든 덱에 동일한 영역 적용
    for i in range(10):
        region_by_id[i] = (x,y,w,h)
    return ('',204)

@app.route('/set_user_region', methods=['POST'])
def set_user_region():
    data = request.get_json()
    uid = int(data['userId'])
    x,y,w,h = data['x'],data['y'],data['w'],data['h']
    # 항상 모든 유저에 동일한 영역 적용
    for i in range(2):
        region_user_by_id[i] = (x,y,w,h)
    return ('',204)

@app.route('/get_regions')
def get_regions():
    return jsonify({
        'user': region_user_by_id,
        'deck': region_by_id
    })

@app.route('/capture_deck')
def capture_deck():
    did = int(request.args.get('deckId'))
    if did not in region_by_id:
        return jsonify({'error':'덱 영역 미지정'}),400
    x,y,w,h = region_by_id[did]
    img = pyautogui.screenshot(region=(x,y,w,h))
    deck_images[did] = img
    buf = io.BytesIO(); img.save(buf,'PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'image':'data:image/png;base64,' + b64})

@app.route('/capture_user')
def capture_user():
    uid = int(request.args.get('userId'))
    if uid not in region_user_by_id:
        return jsonify({'error':'유저정보 영역 미지정'}),400
    x,y,w,h = region_user_by_id[uid]
    img = pyautogui.screenshot(region=(x,y,w,h))
    user_images[uid] = img
    buf = io.BytesIO(); img.save(buf,'PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'image':'data:image/png;base64,' + b64})

@app.route('/upload_slot', methods=['POST'])
def upload_slot():
    data = request.get_json()
    typ = data['type']      # 'user' or 'deck'
    vid = int(data['id'])
    b64data = data['image'].split(',')[1]
    buf = io.BytesIO(base64.b64decode(b64data))
    img = Image.open(buf).convert('RGB')
    if typ=='user':
        user_images[vid] = img
    else:
        deck_images[vid] = img
    return jsonify({'status':'ok'})

@app.route('/reset_user_images', methods=['POST'])
def reset_user_images():
    user_images.clear()
    return jsonify({'status':'user images cleared'})

@app.route('/reset_deck_images', methods=['POST'])
def reset_deck_images():
    deck_images.clear()
    return jsonify({'status':'deck images cleared'})

@app.route('/save', methods=['POST'])
def save():
    global loss_flags
    data = request.get_json()
    loss_flags = data.get('lossFlags', loss_flags)
    suffix = data.get('suffix','').strip()

    if len(deck_images) < 10:
        return jsonify({'error':'10개 덱을 모두 캡처하세요'}),400

    # 폴더 선택
    folder = None
    def tk_th():
        nonlocal folder
        root = tk.Tk(); root.withdraw()
        folder = filedialog.askdirectory(title='저장할 폴더 선택')
        root.destroy()
    t = threading.Thread(target=tk_th); t.start(); t.join()
    if not folder:
        return jsonify({'error':'폴더 선택 취소'}),400

    cw,ch = deck_images[0].size
    seq = [
      ('user',0),('user',1),
      ('deck',0),('deck',5),
      ('deck',1),('deck',6),
      ('deck',2),('deck',7),
      ('deck',3),('deck',8),
      ('deck',4),('deck',9),
    ]

    # raw_composite
    raw = Image.new('RGB',(cw*2,ch*6),'white')
    for idx,(typ,vid) in enumerate(seq):
        row,col = divmod(idx,2)
        x0,y0 = col*cw, row*ch
        img = (user_images if typ=='user' else deck_images).get(vid)
        if img:
            if img.size != (cw,ch):
                img = img.resize((cw,ch))
            raw.paste(img,(x0,y0))
    raw_name = f'raw_composite{suffix}.png' if suffix else 'raw_composite.png'
    raw_path = os.path.join(folder, raw_name)
    raw.save(raw_path)

    # annotated_composite
    ann_base = raw.convert('RGBA')
    overlay  = Image.new('RGBA', ann_base.size,(255,255,255,0))
    draw     = ImageDraw.Draw(overlay)
    for idx,(typ,vid) in enumerate(seq):
        if typ=='deck' and loss_flags[vid]:
            row,col = divmod(idx,2)
            x0,y0 = col*cw, row*ch
            draw.rectangle([(x0,y0),(x0+cw,y0+ch)], fill=(200,200,200,128))
    ann = Image.alpha_composite(ann_base,overlay).convert('RGB')
    ann_name = f'annotated_composite{suffix}.png' if suffix else 'annotated_composite.png'
    ann_path = os.path.join(folder, ann_name)
    ann.save(ann_path)

    return jsonify({'status':'saved','raw':raw_path,'annotated':ann_path})

if __name__ == '__main__':
    app.run(debug=True, port=7777)
