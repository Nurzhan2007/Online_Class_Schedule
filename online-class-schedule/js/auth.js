/* =========================================================
   Authentication - only through the backend:
     POST /api/auth/register, POST /api/auth/login,
     GET /api/auth/me, POST /api/auth/logout

   The server decides everything: passwords are checked with
   PBKDF2 on the server, failed attempts and the 3-attempt
   lockout are counted on the server, roles come from the
   server. There is no local fallback: if the backend cannot
   be reached, nobody is logged in.
   ========================================================= */

// Data written by the old localStorage-only version (including
// plain-text passwords). Removed on start-up; never written again.
const LEGACY_LOCAL_KEYS = [
    "users",
    "currentUser",
    "kbtu_session",
    "kbtu_login_attempts",
    "kbtu_registrations",
    "kbtu_sections"
];

function removeLegacyLocalData() {
    try {
        LEGACY_LOCAL_KEYS.forEach(key => localStorage.removeItem(key));
    } catch (error) {
        // storage unavailable - nothing to remove
    }
}

const Auth = {

    // The logged-in user as returned by the server: {id, name, studentId, email, role}
    user: null,

    async login(email, password) {
        const data = await ApiClient.post(
            "/auth/login",
            { email: email.trim(), password: password },
            { auth: false }
        );

        TokenStore.set(data.access_token, data.expires_in);
        this.user = data.user;

        return data.user;
    },

    // Public registration always creates a *student* (decided by the server).
    register(userData) {
        return ApiClient.post(
            "/auth/register",
            {
                name: userData.name.trim(),
                studentId: userData.studentId.trim(),
                email: userData.email.trim(),
                password: userData.password
            },
            { auth: false }
        );
    },

    // After a page refresh: ask the server who owns the stored token.
    async restore() {
        if (TokenStore.status() !== "valid") {
            TokenStore.clear();
            return null;
        }

        this.user = await ApiClient.get("/auth/me", { notifyUnauthorized: false });

        return this.user;
    },

    // Revoke the token on the server, then forget it locally - even if
    // the server cannot be reached.
    async logout() {
        try {
            if (TokenStore.status() === "valid") {
                await ApiClient.post("/auth/logout", undefined, { notifyUnauthorized: false });
            }
        } catch (error) {
            // already invalid or server unreachable: the local session ends anyway
        } finally {
            this.clearSession();
        }
    },

    clearSession() {
        TokenStore.clear();
        this.user = null;
    },

    role() {
        return this.user ? this.user.role || "student" : null;
    },

    hasRole(...roles) {
        const role = this.role();
        return role !== null && roles.includes(role);
    }
};

/* Local check before navigating: is the stored token still within its
   lifetime? (The server checks the signature, expiry and revocation on
   every request; this only avoids pointless requests with a dead token.) */
function validateAccessToken() {
    const status = TokenStore.status();

    if (status === "valid") {
        return true;
    }

    if (status === "expired" && Auth.user) {
        Auth.clearSession();
        alert(t("auth.sessionExpired"));
    }

    return false;
}

// UI guard; the server enforces the same rule (403 auth.denied).
function requireRole(...allowedRoles) {
    const hadSession = Auth.user !== null;

    if (!validateAccessToken()) {
        // An expired session was already announced by validateAccessToken().
        if (!hadSession) {
            alert(t("auth.loginFirst"));
        }

        if (typeof showLogin === "function") {
            showLogin();
        }

        return false;
    }

    if (!Auth.hasRole(...allowedRoles)) {
        alert(t("auth.denied"));
        return false;
    }

    return true;
}

removeLegacyLocalData();
