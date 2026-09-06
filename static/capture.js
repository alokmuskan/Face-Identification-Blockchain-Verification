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
    if (imageData) {
      imageData.value = dataUrl;
    }

    if (previewImg) {
      previewImg.src = dataUrl;
    }

    if (previewBox) {
      previewBox.hidden = false;
    }

    if (previewNote) {
      previewNote.textContent = note;
    }
  }

  function clearImageData() {
    if (imageData) {
      imageData.value = '';
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(function (track) {
        track.stop();
      });
      stream = null;
    }

    if (cameraBox) {
      cameraBox.hidden = true;
    }
  }

  /*
   * FILE UPLOAD
   *
   * Important:
   * Do NOT convert a selected file to Base64.
   * The browser will submit the file itself through multipart/form-data.
   */
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];

      if (!file) {
        clearImageData();
        return;
      }

      stopCamera();

      // Clear camera Base64 data so the request contains only the file.
      clearImageData();

      // Use an object URL only for preview.
      var previewUrl = URL.createObjectURL(file);

      if (previewImg) {
        previewImg.src = previewUrl;
      }

      if (previewBox) {
        previewBox.hidden = false;
      }

      if (previewNote) {
        previewNote.textContent = 'Selected file: ' + file.name;
      }
    });
  }

  /*
   * CAMERA
   */
  if (cameraBtn) {
    cameraBtn.addEventListener('click', function () {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (previewNote) {
          previewNote.textContent =
            'Camera is not available in this browser.';
        }

        if (previewBox) {
          previewBox.hidden = false;
        }

        return;
      }

      navigator.mediaDevices
        .getUserMedia({
          video: {
            width: 640,
            height: 480
          }
        })
        .then(function (mediaStream) {
          stream = mediaStream;
          video.srcObject = mediaStream;
          cameraBox.hidden = false;

          // Camera mode should not submit an old file.
          if (fileInput) {
            fileInput.value = '';
          }

          clearImageData();
        })
        .catch(function (err) {
          if (previewNote) {
            previewNote.textContent =
              'Camera unavailable: ' + err.message;
          }

          if (previewBox) {
            previewBox.hidden = false;
          }
        });
    });
  }

  /*
   * CAMERA CAPTURE
   */
  if (captureBtn) {
    captureBtn.addEventListener('click', function () {
      if (!video || !video.videoWidth) {
        return;
      }

      var canvas = document.createElement('canvas');

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      canvas
        .getContext('2d')
        .drawImage(video, 0, 0);

      /*
       * Camera images are intentionally sent through image-data.
       * This is the camera path, unlike normal file uploads.
       */
      showPreview(
        canvas.toDataURL('image/png'),
        'Captured from camera.'
      );

      // Make sure a previously selected file is not submitted too.
      if (fileInput) {
        fileInput.value = '';
      }
    });
  }

  /*
   * STOP CAMERA
   */
  if (cameraStop) {
    cameraStop.addEventListener('click', stopCamera);
  }
})();