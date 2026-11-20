/* =========================================================
   Central API client - every request to the backend goes
   through ApiClient (no fetch() anywhere else).

   - same origin by default ("/api"); override for development
     with  window.KBTU_CONFIG = { apiBase: "http://127.0.0.1:8000/api" }
     before this script is loaded
   - attaches the JWT ("Authorization: Bearer ...")
   - parses JSON, turns every failure into an ApiError with a
     translation key (code) that exists in i18n.js
   - never shows server internals: 5xx -> generic message
   ========================================================= */

const API_BASE = (window.KBTU_CONFIG && window.KBTU_CONFIG.apiBase) || "/api";

/* The access token lives in sessionStorage: it survives a page
   refresh but disappears when the tab/browser is closed.
   Passwords are never stored anywhere. */
const TOKEN_KEY = "kbtu_access_token";
const TOKEN_EXPIRES_KEY = "kbtu_access_token_expires";

class ApiError extends Error {
    constructor(status, code, params) {
        super(code);
        this.name = "ApiError";
        this.status = status;      // HTTP status, 0 = network failure
        this.code = code;          // i18n key, e.g. "err.noSeats"
        this.params = params || {};
    }
}

const TokenStore = {

    set(token, expiresInSeconds) {
        sessionStorage.setItem(TOKEN_KEY, token);
        sessionStorage.setItem(TOKEN_EXPIRES_KEY, String(Date.now() + expiresInSeconds * 1000));
    },

    clear() {
        try {
            sessionStorage.removeItem(TOKEN_KEY);
            sessionStorage.removeItem(TOKEN_EXPIRES_KEY);
        } catch (error) {
            // storage unavailable - nothing to clear
        }
    },

    // "none" | "valid" | "expired"
    status() {
        try {
            const token = sessionStorage.getItem(TOKEN_KEY);
            const expiresAt = Number(sessionStorage.getItem(TOKEN_EXPIRES_KEY));

            if (!token || !expiresAt) return "none";
            return Date.now() < expiresAt ? "valid" : "expired";
        } catch (error) {
            return "none";
        }
    },

    get() {
        return this.status() === "valid" ? sessionStorage.getItem(TOKEN_KEY) : null;
    }
};

// Fallback translation key when the response carries no usable code.
function defaultErrorCode(status) {
    if (status === 0) return "err.network";
    if (status >= 500) return "err.server";

    return {
        400: "err.badRequest",
        401: "auth.loginFirst",
        403: "auth.denied",
        404: "err.notFound",
        422: "err.validation",
        429: "auth.locked"
    }[status] || "err.requestFailed";
}

const ApiClient = {

    base: API_BASE,

    // Set by the application: called once a protected request gets 401
    // (expired, revoked or missing token).
    onUnauthorized: null,

    async request(method, path, options) {
        const opts = options || {};
        const auth = opts.auth !== false;
        const headers = { "Accept": "application/json" };

        if (opts.body !== undefined) {
            headers["Content-Type"] = "application/json";
        }

        if (auth) {
            const token = TokenStore.get();

            if (!token) {
                const code = TokenStore.status() === "expired" ? "auth.sessionExpired" : "auth.loginFirst";
                const error = new ApiError(401, code);
                this._unauthorized(error, opts);
                throw error;
            }

            headers["Authorization"] = "Bearer " + token;
        }

        let response;

        try {
            response = await fetch(this.base + path, {
                method: method,
                headers: headers,
                body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
                credentials: "same-origin",
                cache: "no-store"
            });
        } catch (networkError) {
            throw new ApiError(0, "err.network");
        }

        let data = null;

        if (response.status !== 204) {
            try {
                const text = await response.text();
                data = text ? JSON.parse(text) : null;
            } catch (parseError) {
                data = null;   // not JSON (e.g. a proxy error page)
            }
        }

        if (response.ok) {
            return data;
        }

        const detail = data && data.detail;
        let code = detail && typeof detail.code === "string" ? detail.code : null;
        let params = detail && detail.params && typeof detail.params === "object" ? detail.params : {};

        // Server errors: never show details from the server.
        if (response.status >= 500 || !code) {
            code = defaultErrorCode(response.status);
            params = {};
        }

        const error = new ApiError(response.status, code, params);

        if (response.status === 401 && auth) {
            this._unauthorized(error, opts);
        }

        throw error;
    },

    _unauthorized(error, opts) {
        TokenStore.clear();

        if (opts.notifyUnauthorized !== false && typeof this.onUnauthorized === "function") {
            this.onUnauthorized(error);
        }
    },

    get(path, options) {
        return this.request("GET", path, options);
    },

    post(path, body, options) {
        return this.request("POST", path, Object.assign({}, options, { body: body }));
    },

    put(path, body, options) {
        return this.request("PUT", path, Object.assign({}, options, { body: body }));
    },

    delete(path, options) {
        return this.request("DELETE", path, options);
    }
};

/* ---------------------------------------------------------
   Error messages in the current language
   --------------------------------------------------------- */

function formatDuration(totalSeconds) {
    const seconds = Math.max(0, Math.ceil(Number(totalSeconds) || 0));
    const minutes = Math.floor(seconds / 60);

    return minutes + " " + t("time.min") + " " + (seconds % 60) + " " + t("time.sec");
}

function fieldLabel(field) {
    const key = "field." + field;
    const label = t(key);

    return label === key ? field : label;
}

// ApiError (or anything else) -> translated, user-safe text.
function errorMessage(error) {
    if (!(error instanceof ApiError)) {
        console.error(error);
        return t("err.unknown");
    }

    const params = {};

    Object.keys(error.params || {}).forEach(key => {
        const value = error.params[key];

        // Multilingual values such as {en, ru, kk} -> current language.
        params[key] = value && typeof value === "object" && !Array.isArray(value) ? loc(value) : value;
    });

    if (error.code === "auth.locked") {
        params.time = formatDuration(error.params.seconds);
    }

    if (error.code === "err.validation") {
        params.fields = (error.params.fields || []).map(fieldLabel).join(", ");
    }

    const text = t(error.code, params);

    // Unknown code (no translation): use the generic message for the status.
    return text === error.code ? t(defaultErrorCode(error.status)) : text;
}
