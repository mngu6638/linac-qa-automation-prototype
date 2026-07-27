/**
 * Guided film analysis wizard for QA form.
 * Chains upload -> crop -> center -> auto-analyze for fieldsize, collimator, gantry.
 */
(function () {
  'use strict';

  const STEPS = ['upload', 'crop', 'center', 'analyzing'];
  const STEP_LABELS = {
    upload: 'Upload film',
    crop: 'Crop and rotate',
    center: 'Define center / lines',
    analyzing: 'Analyzing',
  };

  let activeType = null;
  let currentStep = 'upload';
  let cropper = null;
  let cropRotation = 0;
  let uploadedData = null;

  // Fieldsize line drawing state
  let lineGroup = 'radiation';
  let lineAwaitingStart = true;
  let lineTempStart = null;
  let wizardLines = { radiation: [], light: [] };

  // Circle drawing state (collimator / gantry)
  let circleData = null;
  let circleHandlers = null;

  function utils() {
    return window.QAFormUtils || {};
  }

  function requestJson(url, options) {
    if (typeof window.requestJson === 'function') {
      return window.requestJson(url, options);
    }
    return utils().requestJson(url, options);
  }

  function postJson(url, payload, options) {
    if (typeof window.postJson === 'function') {
      return window.postJson(url, payload, options);
    }
    return utils().postJson(url, payload, options);
  }

  function postForm(url, formData, options) {
    if (typeof window.postForm === 'function') {
      return window.postForm(url, formData, options);
    }
    return utils().postForm(url, formData, options);
  }

  function cfg() {
    return (window.FILM_WIZARD_CONFIG && window.FILM_WIZARD_CONFIG.types) || {};
  }

  function typeConfig(type) {
    return cfg()[type] || null;
  }

  function el(id) {
    return document.getElementById(id);
  }

  function destroyCropper() {
    if (cropper) {
      cropper.destroy();
      cropper = null;
    }
    cropRotation = 0;
  }

  function setStatus(type, state, text) {
    const c = typeConfig(type);
    if (!c || !c.statusId) return;
    const node = el(c.statusId);
    if (!node) return;
    node.textContent = text || '';
    node.className = 'fw-section-status';
    if (state === 'complete') node.classList.add('fw-complete');
    if (state === 'in-progress') node.classList.add('fw-in-progress');
    const reBtn = c.reanalyzeBtnId ? el(c.reanalyzeBtnId) : null;
    if (reBtn) reBtn.hidden = state !== 'complete';
  }

  function updateStepper() {
    const idx = STEPS.indexOf(currentStep);
    document.querySelectorAll('.fw-step-pill').forEach((pill) => {
      const step = pill.getAttribute('data-step');
      const stepIdx = STEPS.indexOf(step);
      pill.classList.remove('fw-active', 'fw-done');
      if (step === currentStep) pill.classList.add('fw-active');
      else if (stepIdx < idx) pill.classList.add('fw-done');
    });
    const label = el('fwStepLabel');
    if (label) {
      label.textContent = `Step ${Math.min(idx + 1, 3)} of 3: ${STEP_LABELS[currentStep] || ''}`;
    }
  }

  function showStep(step) {
    currentStep = step;
    document.querySelectorAll('.fw-step').forEach((panel) => {
      panel.classList.toggle('fw-step-active', panel.getAttribute('data-step') === step);
    });
    updateStepper();
    updateFooterButtons();
    if (step === 'crop') initCropStep();
    if (step === 'center') initCenterStep();
    if (step === 'analyzing') runAnalyzeStep();
  }

  function updateFooterButtons() {
    const backBtn = el('fwBackBtn');
    const nextBtn = el('fwNextBtn');
    if (!backBtn || !nextBtn) return;
    backBtn.style.display = currentStep === 'upload' || currentStep === 'analyzing' ? 'none' : '';
    nextBtn.style.display = currentStep === 'analyzing' ? 'none' : '';
    if (currentStep === 'upload') nextBtn.textContent = 'Continue';
    else if (currentStep === 'crop') nextBtn.textContent = 'Next';
    else if (currentStep === 'center') nextBtn.textContent = 'Finish';
    if (currentStep === 'upload') {
      const fileInput = el('fwFileInput');
      nextBtn.disabled = !(fileInput && fileInput.files && fileInput.files.length);
    } else {
      nextBtn.disabled = false;
    }
  }

  function openModal(type) {
    activeType = type;
    const c = typeConfig(type);
    if (!c) return;
    uploadedData = null;
    currentStep = 'upload';
    destroyCropper();
    resetUploadForm();
    resetCenterState();
    if (c.profileGraphBtnId) {
      const pBtn = el(c.profileGraphBtnId);
      if (pBtn) pBtn.style.display = 'none';
    }
    if (c.multiRadiusBtnId) {
      const mBtn = el(c.multiRadiusBtnId);
      if (mBtn) mBtn.style.display = 'none';
    }
    const resultImg = el(c.resultImageId);
    if (resultImg) resultImg.removeAttribute('src');
    const title = el('fwTitle');
    if (title) title.textContent = `Run ${c.label} Analysis`;
    el('filmWizardModal').classList.add('fw-open');
    document.querySelectorAll('.fw-center-panel').forEach((p) => {
      p.style.display = p.getAttribute('data-center-type') === c.centerType ? 'block' : 'none';
    });
    const lineCanvas = el('fwLineCanvas');
    const circleCanvas = el('fwCircleCanvas');
    if (lineCanvas) lineCanvas.style.display = c.centerType === 'lines' ? 'block' : 'none';
    if (circleCanvas) circleCanvas.style.display = c.centerType === 'circle' ? 'block' : 'none';
    setStatus(type, 'in-progress', 'In progress...');
    showStep('upload');
  }

  function closeModal() {
    el('filmWizardModal').classList.remove('fw-open');
    destroyCropper();
    teardownCircleCanvas();
    activeType = null;
  }

  function resetUploadForm() {
    const fileInput = el('fwFileInput');
    const dpiStatus = el('fwDpiStatus');
    const manualBlock = el('fwManualDpiBlock');
    const uploadStatus = el('fwUploadStatus');
    if (fileInput) fileInput.value = '';
    if (dpiStatus) dpiStatus.textContent = '';
    if (manualBlock) manualBlock.style.display = 'none';
    if (uploadStatus) uploadStatus.textContent = '';
    const manualDpi = el('fwManualDpi');
    if (manualDpi) manualDpi.value = '';
  }

  function resetCenterState() {
    teardownLineCanvas();
    wizardLines = { radiation: [], light: [] };
    lineGroup = 'radiation';
    lineAwaitingStart = true;
    lineTempStart = null;
    circleData = null;
    const centerStatus = el('fwCenterStatus');
    if (centerStatus) centerStatus.textContent = '';
  }

  function checkDpi(file) {
    const formData = new FormData();
    formData.append('image', file);
    const dpiStatus = el('fwDpiStatus');
    const manualBlock = el('fwManualDpiBlock');
    postForm((window.FILM_WIZARD_CONFIG && window.FILM_WIZARD_CONFIG.checkDpi) || '/check-dpi/', formData)
      .then(({ data }) => {
        if (data.dpi) {
          if (dpiStatus) {
            dpiStatus.textContent = `DPI: ${data.dpi}`;
            dpiStatus.className = 'fw-status';
          }
          if (manualBlock) manualBlock.style.display = 'none';
        } else {
          if (dpiStatus) {
            dpiStatus.textContent = 'DPI not found — enter manually';
            dpiStatus.className = 'fw-error';
          }
          if (manualBlock) manualBlock.style.display = 'block';
        }
      })
      .catch(() => {
        if (dpiStatus) dpiStatus.textContent = 'Could not read DPI';
      });
  }

  function doUpload() {
    const c = typeConfig(activeType);
    const fileInput = el('fwFileInput');
    const uploadStatus = el('fwUploadStatus');
    if (!c || !fileInput || !fileInput.files || !fileInput.files.length) {
      if (uploadStatus) uploadStatus.textContent = 'Please select a file first.';
      return Promise.reject(new Error('No file'));
    }
    const formData = new FormData();
    formData.append('image', fileInput.files[0]);
    const manualDpi = el('fwManualDpi');
    if (manualDpi && manualDpi.value) {
      formData.append('manual_dpi', manualDpi.value);
    }
    if (uploadStatus) uploadStatus.textContent = 'Uploading...';
    return postForm(c.uploadUrl, formData).then(({ response, data }) => {
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Upload failed');
      }
      uploadedData = data;
      if (uploadStatus) uploadStatus.textContent = data.message || 'Upload successful';
      updateFooterButtons();
      return data;
    });
  }

  function loadLatestFilmImage(imgEl, latestApi, croppedPath) {
    return requestJson(latestApi, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(({ data }) => {
      if (!data.success || !data.filename) {
        throw new Error(data.error || 'No film found');
      }
      const ts = Date.now();
      const originalUrl = data.url || `/media/film_uploads/${data.filename}`;
      const base = originalUrl.split('?')[0];

      return new Promise((resolve, reject) => {
        if (croppedPath) {
          imgEl.onerror = () => {
            imgEl.onerror = () => reject(new Error('Image load failed'));
            imgEl.onload = () => resolve(base);
            imgEl.src = `${base}?t=${ts}`;
          };
          imgEl.onload = () => resolve(croppedPath);
          imgEl.src = `${croppedPath}?t=${ts}`;
        } else {
          imgEl.onerror = () => reject(new Error('Image load failed'));
          imgEl.onload = () => resolve(base);
          imgEl.src = `${base}?t=${ts}`;
        }
      });
    });
  }

  function initCropStep() {
    const c = typeConfig(activeType);
    const img = el('fwCropImage');
    const placeholder = el('fwCropPlaceholder');
    if (!c || !img) return;
    destroyCropper();
    if (placeholder) placeholder.style.display = 'none';
    img.style.display = 'block';

    const loadPromise = uploadedData
      ? Promise.resolve().then(() => {
          const url = (uploadedData.url || `/media/film_uploads/${uploadedData.filename}`).split('?')[0];
          return new Promise((resolve, reject) => {
            img.onerror = () => reject(new Error('Load failed'));
            img.onload = () => resolve(url);
            img.crossOrigin = 'anonymous';
            img.src = `${url}?t=${Date.now()}`;
          });
        })
      : loadLatestFilmImage(img, c.latestFilmApi, null);

    loadPromise
      .then(() => {
        cropper = new Cropper(img, {
          aspectRatio: NaN,
          viewMode: 0,
          autoCropArea: 1,
          responsive: true,
        });
      })
      .catch((err) => {
        if (placeholder) placeholder.style.display = 'block';
        img.style.display = 'none';
        alert(`Could not load film image: ${err.message}`);
        showStep('upload');
      });
  }

  function saveCrop() {
    const c = typeConfig(activeType);
    if (!cropper || !c) return Promise.reject(new Error('Cropper not ready'));
    return new Promise((resolve, reject) => {
      cropper.getCroppedCanvas({
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
      }).toBlob((blob) => {
        if (!blob) {
          reject(new Error('Crop failed'));
          return;
        }
        const formData = new FormData();
        formData.append('cropped_image', blob);
        postForm(c.cropUrl, formData)
          .then(({ data }) => {
            if (data.success) resolve(data);
            else reject(new Error(data.error || 'Crop save failed'));
          })
          .catch(reject);
      });
    });
  }

  function rotateCrop(degrees) {
    if (!cropper) return;
    cropRotation = (cropRotation + degrees) % 360;
    cropper.reset();
    cropper.rotateTo(cropRotation);
    cropper.crop();
  }

  // --- Fieldsize line drawing ---
  function ensureWizardLineGroups() {
    if (!wizardLines.radiation) wizardLines.radiation = [];
    if (!wizardLines.light) wizardLines.light = [];
  }

  function setLineGroup(group) {
    lineGroup = group;
    document.querySelectorAll('[data-line-group]').forEach((btn) => {
      btn.classList.toggle('fw-btn-primary', btn.getAttribute('data-line-group') === group);
    });
  }

  function drawWizardLines(previewPoint) {
    const canvas = el('fwLineCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ensureWizardLineGroups();

    if (!lineAwaitingStart && lineTempStart) {
      ctx.beginPath();
      ctx.arc(lineTempStart.x, lineTempStart.y, 4, 0, 2 * Math.PI);
      ctx.fillStyle = 'blue';
      ctx.fill();
    }

    ['radiation', 'light'].forEach((group) => {
      ctx.strokeStyle = group === 'radiation' ? 'red' : 'green';
      ctx.lineWidth = 2;
      (wizardLines[group] || []).forEach((line) => {
        ctx.beginPath();
        ctx.moveTo(line.x1, line.y1);
        ctx.lineTo(line.x2, line.y2);
        ctx.stroke();
      });
    });

    if (!lineAwaitingStart && lineTempStart && previewPoint) {
      ctx.beginPath();
      ctx.moveTo(lineTempStart.x, lineTempStart.y);
      ctx.lineTo(previewPoint.x, previewPoint.y);
      ctx.strokeStyle = lineGroup === 'radiation' ? 'red' : 'green';
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  function teardownLineCanvas() {
    const canvas = el('fwLineCanvas');
    if (!canvas) return;
    if (canvas._fwClickHandler) {
      canvas.removeEventListener('click', canvas._fwClickHandler);
      canvas._fwClickHandler = null;
    }
    if (canvas._fwMoveHandler) {
      canvas.removeEventListener('mousemove', canvas._fwMoveHandler);
      canvas._fwMoveHandler = null;
    }
    canvas.style.pointerEvents = 'none';
  }

  function clearWizardLineGroup(group) {
    ensureWizardLineGroups();
    wizardLines[group] = [];
    if (group === lineGroup) {
      lineAwaitingStart = true;
      lineTempStart = null;
    }
    drawWizardLines();
  }

  function setupLineCanvas() {
    const img = el('fwCenterImage');
    const canvas = el('fwLineCanvas');
    if (!img || !canvas) return;
    teardownLineCanvas();
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = `${img.clientWidth}px`;
    canvas.style.height = `${img.clientHeight}px`;
    canvas.style.pointerEvents = 'auto';
    setLineGroup(lineGroup || 'radiation');

    canvas._fwClickHandler = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      ensureWizardLineGroups();
      if (lineAwaitingStart) {
        lineTempStart = { x, y };
        lineAwaitingStart = false;
      } else {
        wizardLines[lineGroup].push({
          x1: lineTempStart.x,
          y1: lineTempStart.y,
          x2: x,
          y2: y,
        });
        lineAwaitingStart = true;
        lineTempStart = null;
      }
      drawWizardLines();
    };
    canvas._fwMoveHandler = (event) => {
      if (lineAwaitingStart || !lineTempStart) return;
      const rect = canvas.getBoundingClientRect();
      drawWizardLines({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    };
    canvas.addEventListener('click', canvas._fwClickHandler);
    canvas.addEventListener('mousemove', canvas._fwMoveHandler);
    drawWizardLines();
  }

  function validateWizardLines() {
    const canvas = el('fwLineCanvas');
    if (!canvas || canvas.width < 2) {
      return 'Invalid canvas. Please wait for the image to load.';
    }
    if (!lineAwaitingStart || lineTempStart) {
      return 'A line is incomplete. Finish the second click before continuing.';
    }
    const r = (wizardLines.radiation || []).length;
    const l = (wizardLines.light || []).length;
    if (r !== 4 || l !== 4) {
      return 'Please draw exactly 4 radiation lines and 4 light lines.';
    }
    if (r !== l) {
      return 'Number of radiation lines must equal number of light lines.';
    }
    return '';
  }

  function saveWizardLines() {
    const err = validateWizardLines();
    if (err) return Promise.reject(new Error(err));
    const canvas = el('fwLineCanvas');
    const c = typeConfig(activeType);
    return postJson(c.centerUrl, {
      lines: wizardLines,
      image_display_width: canvas.width,
      image_display_height: canvas.height,
    }).then(({ data }) => {
      if (!data.success) throw new Error(data.error || 'Failed to save lines');
      return data;
    });
  }

  // --- Circle drawing (collimator / gantry) ---
  function teardownCircleCanvas() {
    const canvas = el('fwCircleCanvas');
    if (!canvas || !circleHandlers) return;
    canvas.style.pointerEvents = 'none';
    canvas.removeEventListener('mousedown', circleHandlers.down);
    canvas.removeEventListener('mousemove', circleHandlers.move);
    canvas.removeEventListener('mouseup', circleHandlers.up);
    circleHandlers = null;
  }

  function setupCircleCanvas() {
    const img = el('fwCenterImage');
    const canvas = el('fwCircleCanvas');
    if (!img || !canvas) return;
    teardownCircleCanvas();
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = `${img.clientWidth}px`;
    canvas.style.height = `${img.clientHeight}px`;
    canvas.style.pointerEvents = 'auto';
    circleData = { center: null, radius: null, isDrawing: false };

    function redraw(cx, cy, radius, x, y) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (cx == null) return;
      ctx.beginPath();
      ctx.arc(cx, cy, 1.5, 0, 2 * Math.PI);
      ctx.fillStyle = 'red';
      ctx.fill();
      if (radius > 0) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.stroke();
        if (x != null) {
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(x, y);
          ctx.strokeStyle = 'blue';
          ctx.lineWidth = 1;
          ctx.setLineDash([5, 5]);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }
    }

    const onDown = (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      circleData.center = { x, y };
      circleData.isDrawing = true;
      redraw(x, y, 0);
    };
    const onMove = (event) => {
      if (!circleData || !circleData.isDrawing) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const radius = Math.sqrt(
        (x - circleData.center.x) ** 2 + (y - circleData.center.y) ** 2
      );
      circleData.radius = radius;
      redraw(circleData.center.x, circleData.center.y, radius, x, y);
    };
    const onUp = () => {
      if (!circleData) return;
      circleData.isDrawing = false;
      const status = el('fwCenterStatus');
      if (status && circleData.center && circleData.radius) {
        status.textContent = `Circle: center (${Math.round(circleData.center.x)}, ${Math.round(circleData.center.y)}), radius ${Math.round(circleData.radius)}px`;
      }
    };

    canvas.addEventListener('mousedown', onDown);
    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseup', onUp);
    circleHandlers = { down: onDown, move: onMove, up: onUp };
  }

  function saveWizardCircle() {
    if (!circleData || !circleData.center || !circleData.radius) {
      return Promise.reject(new Error('Please define a circle first'));
    }
    const img = el('fwCenterImage');
    const c = typeConfig(activeType);
    const displayWidth = img.clientWidth;
    const displayHeight = img.clientHeight;
    const actualWidth = img.naturalWidth;
    const actualHeight = img.naturalHeight;
    if (actualWidth <= 0 || displayWidth <= 0) {
      return Promise.reject(new Error('Image dimensions invalid. Wait for image to load.'));
    }
    const scaleX = actualWidth / displayWidth;
    const scaleY = actualHeight / displayHeight;
    const payload = {
      center_x: Math.round(circleData.center.x * scaleX),
      center_y: Math.round(circleData.center.y * scaleY),
      radius: Math.round(circleData.radius * Math.max(scaleX, scaleY)),
      image_display_width: displayWidth,
      image_display_height: displayHeight,
      image_actual_width: actualWidth,
      image_actual_height: actualHeight,
      scale_x: scaleX,
      scale_y: scaleY,
    };
    return postJson(c.centerUrl, payload).then(({ data }) => {
      if (!data.success) throw new Error(data.error || 'Failed to save circle');
      return data;
    });
  }

  function initCenterStep() {
    const c = typeConfig(activeType);
    const img = el('fwCenterImage');
    if (!c || !img) return;
    resetCenterState();
    teardownCircleCanvas();

    const lineCanvas = el('fwLineCanvas');
    const circleCanvas = el('fwCircleCanvas');
    if (lineCanvas) lineCanvas.style.display = c.centerType === 'lines' ? 'block' : 'none';
    if (circleCanvas) circleCanvas.style.display = c.centerType === 'circle' ? 'block' : 'none';

    loadLatestFilmImage(img, c.latestFilmApi, c.croppedPath)
      .then(() => {
        if (c.centerType === 'lines') setupLineCanvas();
        else setupCircleCanvas();
      })
      .catch((err) => {
        alert(`Could not load cropped image: ${err.message}`);
        showStep('crop');
      });
  }

  function populateResults(data) {
    const c = typeConfig(activeType);
    if (!c) return;

    const resultImg = el(c.resultImageId);
    if (resultImg && data.result_image_url) {
      resultImg.src = data.result_image_url;
    }

    if (c.profileGraphBtnId && data.profile_graph_url) {
      window[c.profileGraphUrlKey] = data.profile_graph_url;
      const btn = el(c.profileGraphBtnId);
      if (btn) btn.style.display = 'inline-block';
    }
    if (c.multiRadiusBtnId && data.multi_radius_graph_url) {
      window[c.multiRadiusUrlKey] = data.multi_radius_graph_url;
      const btn = el(c.multiRadiusBtnId);
      if (btn) btn.style.display = 'inline-block';
    }

    const resultField = document.querySelector(`[data-field-result="${c.resultField}"]`);
    if (resultField) {
      const value = c.centerType === 'lines' ? data.match_mm : data.circle_diameter_mm;
      if (value != null) {
        resultField.value = value;
        if (typeof window.checkTolerance === 'function') {
          const tol = parseFloat(resultField.getAttribute('data-tol')) || 1;
          const idMatch = resultField.id.match(new RegExp(`${c.resultGroup}_test_(\\d+)`));
          if (idMatch) {
            window.checkTolerance(resultField, tol, c.resultGroup, idMatch[1]);
          }
        }
      }
    }
  }

  function runAnalyzeStep() {
    const c = typeConfig(activeType);
    if (!c) return;
    const errEl = el('fwAnalyzeError');
    const msgEl = el('fwAnalyzeMessage');
    if (errEl) errEl.textContent = '';
    if (msgEl) msgEl.textContent = 'Running analysis...';

    postJson(c.analyzeUrl, {})
      .then(({ data }) => {
        if (!data.success) {
          throw new Error(data.error || 'Analysis failed');
        }
        populateResults(data);
        setStatus(activeType, 'complete', 'Complete');
        closeModal();
      })
      .catch((err) => {
        if (msgEl) msgEl.textContent = '';
        if (errEl) {
          errEl.textContent = err.message || 'Analysis failed';
        }
        const retryBtn = el('fwRetryAnalyzeBtn');
        if (retryBtn) retryBtn.style.display = 'inline-block';
      });
  }

  function goNext() {
    if (currentStep === 'upload') {
      const advance = () => showStep('crop');
      if (uploadedData) {
        advance();
      } else {
        doUpload()
          .then(advance)
          .catch((err) => {
            const uploadStatus = el('fwUploadStatus');
            if (uploadStatus) uploadStatus.textContent = err.message;
          });
      }
      return;
    }
    if (currentStep === 'crop') {
      saveCrop()
        .then(() => {
          destroyCropper();
          showStep('center');
        })
        .catch((err) => alert(`Crop failed: ${err.message}`));
      return;
    }
    if (currentStep === 'center') {
      const c = typeConfig(activeType);
      const savePromise = c.centerType === 'lines' ? saveWizardLines() : saveWizardCircle();
      savePromise
        .then(() => {
          teardownCircleCanvas();
          showStep('analyzing');
        })
        .catch((err) => alert(err.message));
    }
  }

  function goBack() {
    if (currentStep === 'crop') {
      if (window.confirm('Go back to upload? Crop changes will be lost.')) {
        destroyCropper();
        showStep('upload');
      }
      return;
    }
    if (currentStep === 'center') {
      if (window.confirm('Go back to crop? Center markings will need to be redrawn.')) {
        teardownCircleCanvas();
        teardownLineCanvas();
        resetCenterState();
        showStep('crop');
      }
    }
  }

  function bindEvents() {
    const fileInput = el('fwFileInput');
    if (fileInput) {
      fileInput.addEventListener('change', () => {
        uploadedData = null;
        if (fileInput.files && fileInput.files[0]) {
          checkDpi(fileInput.files[0]);
        }
        updateFooterButtons();
      });
    }

    el('fwNextBtn')?.addEventListener('click', goNext);
    el('fwBackBtn')?.addEventListener('click', goBack);
    el('fwCancelBtn')?.addEventListener('click', () => {
      if (window.confirm('Cancel film analysis wizard?')) closeModal();
    });
    el('fwRotateLeftBtn')?.addEventListener('click', () => rotateCrop(-90));
    el('fwRotateRightBtn')?.addEventListener('click', () => rotateCrop(90));

    el('fwLineRadiationBtn')?.addEventListener('click', () => setLineGroup('radiation'));
    el('fwLineLightBtn')?.addEventListener('click', () => setLineGroup('light'));
    el('fwLineClearBtn')?.addEventListener('click', () => clearWizardLineGroup(lineGroup));
    el('fwLineUndoBtn')?.addEventListener('click', () => {
      ensureWizardLineGroups();
      wizardLines[lineGroup].pop();
      lineAwaitingStart = true;
      lineTempStart = null;
      drawWizardLines();
    });
    el('fwCircleClearBtn')?.addEventListener('click', () => {
      circleData = { center: null, radius: null, isDrawing: false };
      const canvas = el('fwCircleCanvas');
      if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
      const status = el('fwCenterStatus');
      if (status) status.textContent = '';
    });

    el('fwRetryAnalyzeBtn')?.addEventListener('click', () => {
      el('fwRetryAnalyzeBtn').style.display = 'none';
      runAnalyzeStep();
    });

    document.querySelectorAll('[data-film-wizard]').forEach((btn) => {
      btn.addEventListener('click', () => openModal(btn.getAttribute('data-film-wizard')));
    });
    document.querySelectorAll('[data-film-reanalyze]').forEach((btn) => {
      btn.addEventListener('click', () => openModal(btn.getAttribute('data-film-reanalyze')));
    });
  }

  function init() {
    if (!el('filmWizardModal')) return;
    bindEvents();
    Object.keys(cfg()).forEach((type) => {
      const c = typeConfig(type);
      const resultImg = c && c.resultImageId ? el(c.resultImageId) : null;
      if (resultImg && resultImg.getAttribute('src')) {
        setStatus(type, 'complete', 'Complete');
      }
    });
  }

  window.FilmWizard = {
    start: openModal,
    goNext,
    goBack,
    cancel: closeModal,
    init,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
