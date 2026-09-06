# Flask application exposing the face identification and blockchain workflows.
from __future__ import annotations

import base64
import binascii
from datetime import datetime

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from config import BASE_DIR, FLASK_DEBUG, HOST, MAX_IMAGE_BYTES, PORT, ensure_dirs
from faceid.engine import FaceEngineError
from services.verification_service import VerificationError, VerificationService

ensure_dirs()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_IMAGE_BYTES
app.config['MAX_FORM_MEMORY_SIZE'] = 5 * 1024 * 1024
service = VerificationService()


@app.template_filter('dt')
def format_timestamp(value):
    # Renders unix timestamps as local time in templates.
    try:
        return datetime.fromtimestamp(float(value)).isoformat(sep=' ', timespec='seconds')
    except (TypeError, ValueError, OSError, OverflowError):
        return value


def image_from_request() -> bytes:
    # Accepts a multipart upload (field: image) or a base64 data URL (field:
    # image_data) captured from the browser camera canvas.
    upload = request.files.get('image')
    if upload is not None and upload.filename:
        data = upload.read()
    else:
        payload = request.form.get('image_data', '')
        if ',' in payload:
            payload = payload.split(',', 1)[1]
        if not payload:
            raise VerificationError('No image was provided. Upload a photo or use the camera.')
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise VerificationError('The captured image could not be decoded.') from exc
    if not data:
        raise VerificationError('The provided image is empty.')
    if len(data) > MAX_IMAGE_BYTES:
        raise VerificationError('The provided image is too large (10 MB max).')
    return data


@app.errorhandler(VerificationError)
def handle_verification_error(exc):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': str(exc)}), 400
    return render_template('error.html', message=str(exc)), 400


@app.errorhandler(FaceEngineError)
def handle_engine_error(exc):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': str(exc)}), 503
    return render_template('error.html', message=str(exc)), 503


@app.route('/health')
def health():
    # Liveness probe for deployment platforms (Render, Railway, Docker, etc.).
    try:
        models_ok = service.engine.models_available()
    except Exception:
        models_ok = False
    return jsonify({
        'status': 'ok' if models_ok else 'degraded',
        'models_available': models_ok,
        'subjects': service.store.count(),
        'blocks': service.blockchain.stats().get('blocks'),
    }), 200 if models_ok else 503


@app.route('/media/<path:relpath>')
def media(relpath):
    # Serves enrollment and probe images stored under data/ (local demo only).
    return send_from_directory(BASE_DIR, relpath)


@app.route('/')
def dashboard():
    return render_template(
        'index.html',
        stats=service.dashboard_stats(),
        subjects=service.store.list_subjects(),
        events=service.recent_events(8),
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    result = None
    error = None
    if request.method == 'POST':
        try:
            result = service.register(request.form.get('name', ''), image_from_request())
        except VerificationError as exc:
            error = str(exc)
    return render_template('register.html', result=result, error=error)


@app.route('/identify', methods=['GET', 'POST'])
def identify():
    result = None
    error = None
    if request.method == 'POST':
        try:
            result = service.identify(image_from_request())
        except VerificationError as exc:
            error = str(exc)
    return render_template('identify.html', result=result, error=error)


@app.route('/ledger')
def ledger():
    blocks = [block.to_dict() for block in reversed(service.blockchain.chain)]
    return render_template('ledger.html', blocks=blocks, stats=service.blockchain.stats())


@app.route('/verify')
def verify_page():
    report = service.blockchain.validate_chain()
    return render_template('verify.html', report=report, stats=service.blockchain.stats())


def build_local_verification_records(events: list) -> list:
    records = []
    for ev in events:
        if ev.get('type') == 'FACE_VERIFICATION':
            records.append(service.build_verification_record(ev))
    return records


@app.route('/history/<subject_id>')
def history(subject_id):
    record = service.history(subject_id)
    if record is None:
        abort(404)
    verification_records = build_local_verification_records(record['events'])
    return render_template(
        'history.html',
        subject=record['subject'],
        events=record['events'],
        verification_records=verification_records,
    )


from config import CONTRACT_ADDRESS

@app.route('/history/<subject_id>/contract')
def history_contract(subject_id):
    record = service.history(subject_id)
    if record is None:
        abort(404)
    report = service.verify_contract(subject_id)
    return render_template(
        'history_contract.html',
        subject=record['subject'],
        report=report,
        config={'CONTRACT_ADDRESS': CONTRACT_ADDRESS},
    )


@app.route('/web-results/<int:block_index>')
def web_results(block_index):
    block = service.blockchain.find_block(block_index)
    if block is None:
        abort(404)
    tx = None
    for t in block.transactions:
        if t.get('web_search_results'):
            tx = t
            break
    if tx is None:
        abort(404)
    return render_template('web_results.html', block=block.to_dict(), tx=tx)


@app.route('/api/status')
def api_status():
    return jsonify({
        'ok': True,
        'models_available': service.engine.models_available(),
        'subjects': service.store.count(),
        'blockchain': service.blockchain.stats(),
    })


@app.route('/api/register', methods=['POST'])
def api_register():
    outcome = service.register(request.form.get('name', ''), image_from_request())
    return jsonify({'ok': True, **outcome}), 201


@app.route('/api/identify', methods=['POST'])
def api_identify():
    outcome = service.identify(image_from_request())
    return jsonify({'ok': True, **outcome})


@app.route('/api/chain')
def api_chain():
    return jsonify({
        'ok': True,
        'stats': service.blockchain.stats(),
        'blocks': [block.to_dict() for block in service.blockchain.chain],
    })


@app.route('/api/chain/validate')
def api_chain_validate():
    return jsonify({'ok': True, **service.blockchain.validate_chain()})


@app.route('/api/history/<subject_id>')
def api_history(subject_id):
    record = service.history(subject_id)
    if record is None:
        return jsonify({'ok': False, 'error': 'Unknown subject.'}), 404
    return jsonify({'ok': True, **record})


@app.route('/api/history/<subject_id>/contract')
def api_history_contract(subject_id):
    return jsonify({'ok': True, **service.verify_contract(subject_id)})


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=FLASK_DEBUG, use_reloader=False)
