/* Shared QA form frontend helpers. */
(function () {
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i += 1) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === `${name}=`) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) {
      return input.value;
    }
    return getCookie('csrftoken');
  }

  function withCsrfHeader(headers) {
    const merged = { ...(headers || {}) };
    if (!Object.prototype.hasOwnProperty.call(merged, 'X-CSRFToken')) {
      merged['X-CSRFToken'] = getCsrfToken();
    }
    return merged;
  }

  function requestJson(url, options) {
    const opts = options || {};
    const headers = withCsrfHeader(opts.headers);
    return fetch(url, { ...opts, headers }).then((response) =>
      response
        .json()
        .catch(() => ({}))
        .then((data) => ({ response, data }))
    );
  }

  function postJson(url, payload, options) {
    const opts = options || {};
    return requestJson(url, {
      ...opts,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(opts.headers || {}),
      },
      body: JSON.stringify(payload || {}),
    });
  }

  function postForm(url, formData, options) {
    const opts = options || {};
    return requestJson(url, {
      ...opts,
      method: 'POST',
      body: formData,
    });
  }

  window.QAFormUtils = {
    getCookie,
    getCsrfToken,
    requestJson,
    postJson,
    postForm,
  };
})();
