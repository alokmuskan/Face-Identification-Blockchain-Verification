(function () {
  var fileInput = document.getElementById('file-input');
  var cameraBtn = document.getElementById('camera-btn');
  var cameraBox = document.getElementById('camera-box');
  var cameraStop = document.getElementById('camera-stop');
  var captureBtn = document.getElementById('capture-btn');
  var video = document.getElementById('camera-video');
  var previewBox = document.getElementById('preview-box');
  var previewImg = document.getElementById('preview-img');
  var previewNote = document.getElementById('preview-note');
  var imageData = document.getElementById('image-data');
  var stream = null;

  function showPreview(dataUrl, note) {
    imageData.value = dataUrl;
    previewImg.src = dataUrl;
    previewBox.hidden = false;
    previewNote.textContent = note;
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
    }
    cameraBox.hidden = true;
  }

  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) { return; }
      var reader = new FileReader();
      reader.onload = function () {
        stopCamera();
        showPreview(String(reader.result), 'Selected file: ' + file.name);
      };
      reader.readAsDataURL(file);
    });
  }

  if (cameraBtn) {
    cameraBtn.addEventListener('click', function () {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        previewNote.textContent = 'Camera is not available in this browser.';
        previewBox.hidden = false;
        return;
      }
      navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } }).then(function (mediaStream) {
        stream = mediaStream;
        video.srcObject = mediaStream;
        cameraBox.hidden = false;
      }).catch(function (err) {
        previewNote.textContent = 'Camera unavailable: ' + err.message;
        previewBox.hidden = false;
      });
    });
  }

  if (captureBtn) {
    captureBtn.addEventListener('click', function () {
      if (!video.videoWidth) { return; }
      var canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      showPreview(canvas.toDataURL('image/png'), 'Captured from camera.');
    });
  }

  if (cameraStop) {
    cameraStop.addEventListener('click', stopCamera);
  }
})();
