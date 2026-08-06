from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Lock
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.config import load_settings, normalized_provider, require_llm_credentials
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


HTML = r'''<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ScholarLens · RAG Demo</title>
  <style>
    :root{--ink:#17223b;--muted:#68738b;--line:#dfe5ee;--paper:#f6f8fc;--card:#fff;--blue:#3159d8;--blue2:#6b8cff;--mint:#1a9b78;--shadow:0 18px 50px rgba(25,42,80,.12)}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 12% 8%,#e8efff 0,transparent 28%),radial-gradient(circle at 90% 90%,#e0f7ef 0,transparent 26%),var(--paper);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh}
    .shell{width:min(1180px,calc(100% - 32px));margin:24px auto;display:grid;grid-template-columns:300px 1fr;min-height:calc(100vh - 48px);background:rgba(255,255,255,.78);border:1px solid rgba(255,255,255,.9);box-shadow:var(--shadow);border-radius:24px;overflow:hidden;backdrop-filter:blur(16px)}
    aside{padding:28px 22px;border-right:1px solid var(--line);background:rgba(250,252,255,.82)}
    .brand{display:flex;align-items:center;gap:12px;font-size:20px;font-weight:750;letter-spacing:-.4px}.mark{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;color:#fff;background:linear-gradient(135deg,var(--blue),var(--blue2));box-shadow:0 8px 20px rgba(49,89,216,.28)}
    .eyebrow{margin:32px 0 10px;color:var(--muted);font-size:11px;font-weight:750;letter-spacing:1.4px;text-transform:uppercase}.status{display:flex;align-items:center;gap:8px;font-weight:650}.dot{width:9px;height:9px;border-radius:50%;background:#f0a33a;box-shadow:0 0 0 4px #fff2dc}.dot.ok{background:var(--mint);box-shadow:0 0 0 4px #daf4eb}
    .meta{margin-top:12px;border:1px solid var(--line);border-radius:14px;background:#fff;padding:13px}.meta-row{display:flex;justify-content:space-between;gap:10px;padding:5px 0;color:var(--muted);font-size:12px}.meta-row b{max-width:155px;color:var(--ink);font-weight:650;text-align:right;overflow-wrap:anywhere}
    .samples{display:grid;gap:9px}.sample{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:13px;padding:11px 12px;text-align:left;font:inherit;font-size:12.5px;cursor:pointer;transition:.18s}.sample:hover{border-color:#9bb0f7;transform:translateY(-1px);box-shadow:0 7px 16px rgba(49,89,216,.09)}
    .note{margin-top:22px;padding:12px;border-radius:12px;background:#edf2ff;color:#45577d;font-size:11.5px}
    main{min-width:0;display:flex;flex-direction:column}.hero{padding:29px 34px 20px;border-bottom:1px solid var(--line)}.hero h1{margin:0;font-size:25px;letter-spacing:-.7px}.hero p{margin:5px 0 0;color:var(--muted)}
    #chat{flex:1;overflow:auto;padding:28px 34px;display:flex;flex-direction:column;gap:18px;min-height:440px;max-height:calc(100vh - 235px)}.empty{margin:auto;text-align:center;max-width:500px;color:var(--muted)}.empty-icon{width:72px;height:72px;margin:0 auto 18px;display:grid;place-items:center;border-radius:22px;background:linear-gradient(135deg,#e8eeff,#e4f8f2);font-size:30px}.empty h2{color:var(--ink);margin:0 0 8px;font-size:21px}.msg{display:flex;gap:12px;max-width:88%;animation:up .25s ease}.msg.user{align-self:flex-end;flex-direction:row-reverse}.avatar{flex:0 0 34px;height:34px;border-radius:11px;display:grid;place-items:center;background:#e8edff;color:var(--blue);font-weight:800}.user .avatar{background:var(--blue);color:#fff}.bubble{padding:13px 15px;border:1px solid var(--line);border-radius:5px 17px 17px 17px;background:#fff;white-space:pre-wrap;overflow-wrap:anywhere}.user .bubble{background:var(--blue);color:#fff;border-color:var(--blue);border-radius:17px 5px 17px 17px}.error .bubble{border-color:#f0b8b8;background:#fff5f5;color:#9a3333}
    .typing{display:flex;gap:5px;padding:7px 2px}.typing i{width:7px;height:7px;background:#8591a8;border-radius:50%;animation:pulse 1s infinite}.typing i:nth-child(2){animation-delay:.15s}.typing i:nth-child(3){animation-delay:.3s}
    .comparison{width:100%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;animation:up .25s ease}.answer-card{min-width:0;border:1px solid var(--line);border-radius:17px;background:#fff;overflow:hidden;box-shadow:0 7px 20px rgba(30,45,80,.06)}.answer-head{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;border-bottom:1px solid var(--line);font-size:12px;font-weight:800}.answer-head span{font-size:10px;padding:3px 7px;border-radius:999px}.baseline .answer-head{color:#3159d8;background:#f0f4ff}.baseline .answer-head span{background:#dce6ff}.corrupted .answer-head{color:#b54747;background:#fff3f3}.corrupted .answer-head span{background:#fbdede}.repaired .answer-head{color:#168061;background:#effaf6}.repaired .answer-head span{background:#d6f3e9}.answer-body{padding:14px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;min-height:120px}.answer-card.failed .answer-body{color:#a03e3e;background:#fffafa}
    .composer{padding:18px 34px 24px;border-top:1px solid var(--line);background:rgba(255,255,255,.7)}.box{display:flex;align-items:flex-end;gap:10px;padding:8px 8px 8px 15px;background:#fff;border:1px solid #cad3e2;border-radius:17px;box-shadow:0 7px 22px rgba(30,45,80,.07)}textarea{flex:1;resize:none;border:0;outline:0;min-height:42px;max-height:130px;padding:10px 0;background:transparent;color:var(--ink);font:inherit}button.send{width:43px;height:43px;border:0;border-radius:13px;background:linear-gradient(135deg,var(--blue),#5579ed);color:#fff;font-size:20px;cursor:pointer}button.send:disabled{opacity:.45;cursor:not-allowed}.hint{margin-top:7px;color:#8993a6;font-size:11px;text-align:center}
    @keyframes pulse{0%,70%,100%{opacity:.35;transform:translateY(0)}35%{opacity:1;transform:translateY(-3px)}}@keyframes up{from{opacity:0;transform:translateY(7px)}}
    @media(max-width:950px){.comparison{grid-template-columns:1fr}}@media(max-width:800px){.shell{width:100%;margin:0;min-height:100vh;border-radius:0;grid-template-columns:1fr}aside{display:none}.hero{padding:22px 20px 16px}#chat{padding:20px;max-height:calc(100vh - 210px)}.composer{padding:14px 18px 20px}.msg{max-width:96%}}
  </style>
</head>
<body><div class="shell">
  <aside>
    <div class="brand"><span class="mark">S</span><span>ScholarLens</span></div>
    <div class="eyebrow">System status</div><div class="status"><span id="dot" class="dot"></span><span id="statusText">Đang kết nối…</span></div>
    <div class="meta"><div class="meta-row"><span>Provider</span><b id="provider">—</b></div><div class="meta-row"><span>Model</span><b id="model">—</b></div><div class="meta-row"><span>Baseline</span><b id="baselineDocs">—</b></div><div class="meta-row"><span>Corrupted</span><b id="corruptedDocs">—</b></div><div class="meta-row"><span>Repaired</span><b id="repairedDocs">—</b></div></div>
    <div class="eyebrow">Câu hỏi gợi ý</div><div class="samples">
      <button class="sample">Hãy liệt kê các bài báo liên quan đến RAG và DOI.</button>
      <button class="sample">Bài báo nào nói về hallucination? Hãy tóm tắt.</button>
      <button class="sample">Ai là tác giả của bài Reliable retrieval-augmented feature generation?</button>
    </div>
    <div class="note">Agent chỉ trả lời dựa trên corpus Crossref đã được lập chỉ mục và sử dụng semantic search hoặc exact lookup.</div>
  </aside>
  <main><header class="hero"><h1>RAG Data Quality Comparator</h1><p>Một câu hỏi · Ba trạng thái dữ liệu · Cùng một LLM và evaluation context</p></header>
    <section id="chat"><div id="empty" class="empty"><div class="empty-icon">⌕</div><h2>So sánh Baseline · Corrupted · Repaired</h2><p>Đặt một câu hỏi. Ba agent sẽ truy vấn ba index độc lập và trả kết quả song song để quan sát ảnh hưởng của data corruption.</p></div></section>
    <footer class="composer"><div class="box"><textarea id="input" rows="1" placeholder="Nhập câu hỏi về corpus…"></textarea><button id="send" class="send" title="Gửi">↑</button></div><div class="hint">Enter để gửi · Shift + Enter để xuống dòng</div></footer>
  </main>
</div>
<script>
const chat=document.querySelector('#chat'), input=document.querySelector('#input'), send=document.querySelector('#send'); let busy=false;
function add(role,text,error=false){document.querySelector('#empty')?.remove();const row=document.createElement('div');row.className=`msg ${role}${error?' error':''}`;const av=document.createElement('div');av.className='avatar';av.textContent=role==='user'?'U':'S';const b=document.createElement('div');b.className='bubble';b.textContent=text;row.append(av,b);chat.append(row);chat.scrollTop=chat.scrollHeight;return row}
function typing(){const row=add('agent','');row.querySelector('.bubble').innerHTML='<span class="typing"><i></i><i></i><i></i></span>';return row}
function addComparison(data){const grid=document.createElement('div');grid.className='comparison';for(const [key,label,badge] of [['baseline','Baseline','CLEAN'],['corrupted','Corrupted','BROKEN'],['repaired','Repaired','RECOVERED']]){const value=data[key]||{};const card=document.createElement('article');card.className=`answer-card ${key}${value.error?' failed':''}`;const head=document.createElement('div');head.className='answer-head';head.append(document.createTextNode(label));const tag=document.createElement('span');tag.textContent=badge;head.append(tag);const body=document.createElement('div');body.className='answer-body';body.textContent=value.error?value.error:(value.answer||'Không có câu trả lời.');card.append(head,body);grid.append(card)}chat.append(grid);chat.scrollTop=chat.scrollHeight}
async function ask(text){if(!text||busy)return;busy=true;send.disabled=true;add('user',text);input.value='';input.style.height='auto';const wait=typing();try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})});const data=await r.json();wait.remove();if(!r.ok) add('agent',data.error||'Không thể xử lý yêu cầu.',true);else addComparison(data.results)}catch(e){wait.remove();add('agent','Không kết nối được với backend: '+e.message,true)}finally{busy=false;send.disabled=false;input.focus()}}
send.onclick=()=>ask(input.value.trim());input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask(input.value.trim())}});input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,130)+'px'});document.querySelectorAll('.sample').forEach(b=>b.onclick=()=>ask(b.textContent.trim()));
fetch('/api/status').then(r=>r.json()).then(s=>{document.querySelector('#provider').textContent=s.provider;document.querySelector('#model').textContent=s.model;document.querySelector('#baselineDocs').textContent=s.states.baseline.documents+' docs';document.querySelector('#corruptedDocs').textContent=s.states.corrupted.documents+' docs';document.querySelector('#repairedDocs').textContent=s.states.repaired.documents+' docs';document.querySelector('#statusText').textContent='Ba index sẵn sàng';document.querySelector('#dot').classList.add('ok')}).catch(()=>document.querySelector('#statusText').textContent='Mất kết nối');
</script></body></html>'''


def _load_comparison_indexes(settings) -> dict[str, LocalEmbeddingIndex]:
    """Load or build isolated Chroma collections for all three data states."""
    data_dir = settings.paths.project_dir / "data"
    manifest_dir = data_dir / "embeddings" / "ui"
    chroma_dir = data_dir / "chroma_ui"
    manifests = {
        "baseline": manifest_dir / "baseline.json",
        "corrupted": manifest_dir / "corrupted.json",
        "repaired": manifest_dir / "repaired.json",
    }
    csv_paths = {
        "baseline": settings.paths.clean_csv,
        "corrupted": settings.paths.corrupted_clean_csv,
        "repaired": settings.paths.repaired_clean_csv,
    }
    ui_paths = replace(
        settings.paths,
        chroma_dir=chroma_dir,
        embeddings_json=manifests["baseline"],
        corrupted_embeddings_json=manifests["corrupted"],
        repaired_embeddings_json=manifests["repaired"],
    )
    ui_settings = replace(
        settings,
        paths=ui_paths,
        baseline_collection_name="ui-baseline",
        corrupted_collection_name="ui-corrupted",
        repaired_collection_name="ui-repaired",
    )

    indexes: dict[str, LocalEmbeddingIndex] = {}
    for state in ("baseline", "corrupted", "repaired"):
        source_path = csv_paths[state]
        manifest_path = manifests[state]
        if not source_path.exists():
            raise FileNotFoundError(
                f"Missing {state} dataset: {source_path}. Run phase1 and corruption_flow first."
            )
        if manifest_path.exists():
            try:
                indexes[state] = LocalEmbeddingIndex.load(ui_settings, manifest_path)
                continue
            except Exception as exc:
                print(f"Cannot reuse {state} UI index ({exc}); rebuilding...")

        dataframe = pd.read_csv(source_path, keep_default_na=False)
        if dataframe.empty:
            raise RuntimeError(f"The {state} dataset is empty: {source_path}")
        print(f"Building {state} UI index from {source_path.name}...")
        indexes[state] = LocalEmbeddingIndex.build(
            dataframe,
            ui_settings,
            embeddings_output_path=manifest_path,
        )
    return indexes


class DemoHandler(BaseHTTPRequestHandler):
    agents: dict[str, Any] = {}
    status: dict[str, Any] = {}
    agent_lock = Lock()

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self._json(200, self.status)
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = str(payload.get("question", "")).strip()
            if not question:
                raise ValueError("Câu hỏi không được để trống")
            results: dict[str, dict[str, str]] = {}

            def invoke(state: str) -> tuple[str, dict[str, str]]:
                try:
                    return state, {"answer": run_agent_question(self.agents[state], question)}
                except Exception as state_exc:
                    message = str(state_exc)
                    if "402" in message:
                        message = "OpenRouter không đủ credit. Giảm LLM_MAX_TOKENS hoặc nạp thêm credit."
                    elif "401" in message:
                        message = "API key OpenRouter không hợp lệ."
                    return state, {"error": message}

            # Separate agents/indexes can safely execute in parallel and this
            # keeps the three-way comparison responsive.
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(invoke, state) for state in self.agents]
                for future in as_completed(futures):
                    state, result = future.result()
                    results[state] = result
            self._json(200, {"results": results})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            message = str(exc)
            if "402" in message:
                message = "OpenRouter không đủ credit hoặc max token quá cao. Kiểm tra LLM_MAX_TOKENS trong .env."
            elif "401" in message:
                message = "API key không hợp lệ. Kiểm tra OPENROUTER_API_KEY trong .env."
            self._json(500, {"error": message})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[UI] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the local ScholarLens RAG demo UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    settings = load_settings(ROOT)
    require_llm_credentials(settings)
    indexes = _load_comparison_indexes(settings)
    DemoHandler.agents = {state: build_agent(settings, index) for state, index in indexes.items()}
    DemoHandler.status = {
        "provider": normalized_provider(settings),
        "model": settings.model_name,
        "states": {
            state: {"collection": index.collection_name, "documents": len(index.documents)}
            for state, index in indexes.items()
        },
    }
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"ScholarLens UI is ready: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping UI...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
