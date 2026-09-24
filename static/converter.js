/**
 * Image Tools — shared converter script.
 *
 * Enhances every <form data-converter> on the page. All tool-specific
 * configuration comes from data attributes rendered by converter.html:
 *
 *   data-endpoint     API URL to POST to, e.g. "/api/jpgtopng"
 *   data-extensions   comma-separated allowed extensions, e.g. ".jpg,.jpeg"
 *   data-output-ext   extension of the converted file, e.g. "png"
 *   data-label        human-readable input type, e.g. "JPG"
 *   data-max-bytes    optional upload limit in bytes (defaults to 5 MB)
 */
(function () {
  "use strict";

  var DEFAULT_MAX_BYTES = 5 * 1024 * 1024;

  /** Format a byte count as a short human-readable string. */
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  /** Return the lower-cased extension of a file name, including the dot. */
  function getExtension(fileName) {
    var dot = fileName.lastIndexOf(".");
    return dot === -1 ? "" : fileName.slice(dot).toLowerCase();
  }

  /**
   * Extract the file name from a Content-Disposition header.
   * Supports RFC 5987 `filename*=UTF-8''...` as well as plain `filename=...`.
   */
  function filenameFromDisposition(header) {
    if (!header) return null;

    var extended = /filename\*\s*=\s*(?:[\w-]+)?'[^']*'([^;]+)/i.exec(header);
    if (extended) {
      try {
        return decodeURIComponent(extended[1].trim().replace(/^"|"$/g, ""));
      } catch (err) {
        /* fall through to the plain filename parameter */
      }
    }

    var plain = /filename\s*=\s*("([^"]*)"|[^;]+)/i.exec(header);
    if (plain) {
      var name = (plain[2] !== undefined ? plain[2] : plain[1]).trim();
      return name || null;
    }
    return null;
  }

  /** Read a human-readable error message from a failed response. */
  function readErrorMessage(response) {
    var fallback = response.statusText
      ? "Error " + response.status + ": " + response.statusText
      : "Request failed with status " + response.status + ".";

    return response
      .json()
      .then(function (data) {
        return data && typeof data.error === "string" && data.error ? data.error : fallback;
      })
      .catch(function () {
        return fallback;
      });
  }

  /** Trigger a browser download for a Blob, then release its object URL. */
  function downloadBlob(blob, fileName) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Revoke on the next tick so the browser has started the download.
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  function initConverter(form) {
    var config = {
      endpoint: form.dataset.endpoint,
      extensions: (form.dataset.extensions || "")
        .split(",")
        .map(function (ext) { return ext.trim().toLowerCase(); })
        .filter(Boolean),
      outputExt: form.dataset.outputExt || "bin",
      label: form.dataset.label || "image",
      maxBytes: Number(form.dataset.maxBytes) || DEFAULT_MAX_BYTES,
    };

    var input = form.querySelector('input[type="file"]');
    var dropzone = form.querySelector("[data-dropzone]");
    var fileInfo = form.querySelector("[data-file-info]");
    var status = form.querySelector("[data-status]");
    var submit = form.querySelector("[data-submit]");
    var submitText = submit.textContent.trim();

    var selectedFile = null;
    var busy = false;

    function setStatus(message, kind) {
      status.textContent = message || "";
      status.classList.toggle("is-error", kind === "error");
      status.classList.toggle("is-success", kind === "success");
    }

    function setBusy(isBusy) {
      busy = isBusy;
      submit.disabled = isBusy;
      submit.textContent = isBusy ? "Converting…" : submitText;
      form.setAttribute("aria-busy", String(isBusy));
    }

    /** Return an error message for an invalid file, or null if it is OK. */
    function validate(file) {
      if (!file) {
        return "Please choose a " + config.label + " file first.";
      }
      if (config.extensions.indexOf(getExtension(file.name)) === -1) {
        return "Please choose a " + config.label + " file (" + config.extensions.join(", ") + ").";
      }
      if (file.size > config.maxBytes) {
        return "The file is " + formatBytes(file.size) + ". The maximum size is " +
          formatBytes(config.maxBytes) + ".";
      }
      return null;
    }

    function selectFile(file) {
      selectedFile = file || null;

      if (selectedFile) {
        fileInfo.textContent = "Selected: " + selectedFile.name + " (" + formatBytes(selectedFile.size) + ")";
        fileInfo.hidden = false;
      } else {
        fileInfo.textContent = "";
        fileInfo.hidden = true;
      }

      var error = selectedFile ? validate(selectedFile) : null;
      setStatus(error, error ? "error" : null);
    }

    // --- File picker ------------------------------------------------------
    input.addEventListener("change", function () {
      selectFile(input.files && input.files[0]);
    });

    // --- Drag and drop ----------------------------------------------------
    ["dragenter", "dragover"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
        dropzone.classList.add("is-dragover");
      });
    });

    ["dragleave", "dragend"].forEach(function (type) {
      dropzone.addEventListener(type, function (event) {
        // Ignore dragleave events fired when moving over child elements.
        if (event.relatedTarget && dropzone.contains(event.relatedTarget)) return;
        dropzone.classList.remove("is-dragover");
      });
    });

    dropzone.addEventListener("drop", function (event) {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
      var files = event.dataTransfer && event.dataTransfer.files;
      if (!files || files.length === 0) return;
      if (files.length > 1) {
        setStatus("Please drop a single file.", "error");
        return;
      }
      // Keep the native input in sync so the form state is consistent.
      try {
        input.files = files;
      } catch (err) {
        /* Older browsers: input.files is read-only; selectedFile still works. */
      }
      selectFile(files[0]);
    });

    // --- Submit -----------------------------------------------------------
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (busy) return;

      var error = validate(selectedFile);
      if (error) {
        setStatus(error, "error");
        input.focus();
        return;
      }

      var formData = new FormData();
      formData.append("image", selectedFile, selectedFile.name);

      setStatus("");
      setBusy(true);

      fetch(config.endpoint, { method: "POST", body: formData })
        .then(function (response) {
          if (!response.ok) {
            return readErrorMessage(response).then(function (message) {
              throw new Error(message);
            });
          }
          var fileName =
            filenameFromDisposition(response.headers.get("Content-Disposition")) ||
            "converted." + config.outputExt;
          return response.blob().then(function (blob) {
            downloadBlob(blob, fileName);
            setStatus("Done! Downloaded " + fileName + ".", "success");
          });
        })
        .catch(function (err) {
          var message = err instanceof TypeError
            ? "Could not reach the server. Please check your connection and try again."
            : err.message;
          setStatus(message, "error");
        })
        .then(function () {
          setBusy(false);
        });
    });
  }

  // Prevent the browser from opening a file dropped outside the drop zone.
  ["dragover", "drop"].forEach(function (type) {
    window.addEventListener(type, function (event) {
      event.preventDefault();
    });
  });

  document.querySelectorAll("form[data-converter]").forEach(initConverter);
})();
