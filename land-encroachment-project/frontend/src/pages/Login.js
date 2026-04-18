import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getLocalizedText } from "../config/appContent";

const initialLogin = {
  username: "",
  password: "",
};

const initialRegister = {
  fullName: "",
  username: "",
  password: "",
};

export default function Login({ auth, onLogin, onRegister }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [language, setLanguage] = useState(auth?.language || "en");
  const [loginForm, setLoginForm] = useState(initialLogin);
  const [registerForm, setRegisterForm] = useState(initialRegister);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleLoginSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const result = await onLogin?.({
      language,
      username: loginForm.username.trim(),
      password: loginForm.password,
    });

    setBusy(false);
    if (!result?.ok) {
      setError(result?.message || "Unable to sign in.");
      return;
    }

    navigate(result.redirectTo || "/dashboard");
  }

  async function handleRegisterSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const result = await onRegister?.({
      language,
      fullName: registerForm.fullName.trim(),
      username: registerForm.username.trim(),
      password: registerForm.password,
    });

    setBusy(false);
    if (!result?.ok) {
      setError(result?.message || "Unable to create account.");
      return;
    }

    navigate(result.redirectTo || "/dashboard");
  }

  return (
    <div className="login-screen">
      <div className="login-orb login-orb-left" />
      <div className="login-orb login-orb-right" />

      <section className="login-panel login-panel-single">
        <div className="login-form login-form-refined">
          <p className="section-eyebrow">
            {getLocalizedText(language, "Chennai Land Intelligence", "Chennai Land Intelligence")}
          </p>
          <h1 className="login-panel-title">Land Encroachment Monitoring System</h1>

          <div className="language-switch">
            <button
              className={language === "en" ? "chip-button chip-button-active" : "chip-button"}
              onClick={() => setLanguage("en")}
              type="button"
            >
              English
            </button>
            <button
              className={language === "ta" ? "chip-button chip-button-active" : "chip-button"}
              onClick={() => setLanguage("ta")}
              type="button"
            >
              Tamil
            </button>
          </div>

          <div className="auth-mode-switch">
            <button
              className={mode === "login" ? "chip-button chip-button-active" : "chip-button"}
              onClick={() => {
                setMode("login");
                setError("");
              }}
              type="button"
            >
              Login
            </button>
            <button
              className={mode === "register" ? "chip-button chip-button-active" : "chip-button"}
              onClick={() => {
                setMode("register");
                setError("");
              }}
              type="button"
            >
              Register
            </button>
          </div>

          {mode === "login" ? (
            <form className="auth-form" onSubmit={handleLoginSubmit}>
              <div>
                <p className="section-eyebrow">Secure access</p>
                <h2 className="login-form-title">Sign in to your workspace</h2>
              </div>

              <label className="form-field">
                <span>Username</span>
                <input
                  value={loginForm.username}
                  onChange={(event) =>
                    setLoginForm((current) => ({
                      ...current,
                      username: event.target.value,
                    }))
                  }
                  placeholder="Enter your username"
                  type="text"
                />
              </label>

              <label className="form-field">
                <span>Password</span>
                <input
                  value={loginForm.password}
                  onChange={(event) =>
                    setLoginForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Enter your password"
                  type="password"
                />
              </label>

              {error ? <div className="status-error">{error}</div> : null}

              <button disabled={busy} type="submit">
                {busy ? "Signing in..." : "Enter workspace"}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={handleRegisterSubmit}>
              <div>
                <p className="section-eyebrow">Citizen onboarding</p>
                <h2 className="login-form-title">Create a new account</h2>
                <p className="body-copy">
                  Use a simple username like `sathiyasri_1` or `sathiya.ri`.
                  Do not use `@` or spaces.
                </p>
              </div>

              <label className="form-field">
                <span>Full name</span>
                <input
                  value={registerForm.fullName}
                  onChange={(event) =>
                    setRegisterForm((current) => ({
                      ...current,
                      fullName: event.target.value,
                    }))
                  }
                  placeholder="Enter your full name"
                  type="text"
                />
              </label>

              <label className="form-field">
                <span>Username</span>
                <input
                  value={registerForm.username}
                  onChange={(event) =>
                    setRegisterForm((current) => ({
                      ...current,
                      username: event.target.value,
                    }))
                  }
                  placeholder="Choose a username"
                  type="text"
                />
              </label>

              <label className="form-field">
                <span>Password</span>
                <input
                  value={registerForm.password}
                  onChange={(event) =>
                    setRegisterForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Use at least 8 characters"
                  type="password"
                />
              </label>

              {error ? <div className="status-error">{error}</div> : null}

              <button disabled={busy} type="submit">
                {busy ? "Creating account..." : "Create account"}
              </button>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}
