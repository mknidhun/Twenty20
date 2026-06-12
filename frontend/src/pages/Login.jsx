import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatError } from "@/utils/api";
import { AUTH } from "@/constants/testIds";
import { Eye, EyeSlash } from "@phosphor-icons/react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.email, form.password);
      navigate("/dashboard");
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-background">
      {/* Left: Hero */}
      <div
        className="hidden lg:flex flex-1 flex-col justify-between p-12 relative"
        style={{
          backgroundImage: "url(https://images.unsplash.com/photo-1593113598332-cd288d649433?q=80&w=2000&auto=format&fit=crop)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-black/60" />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <img src="/logo-full-light.png" alt="Twenty20 Charity Group Wariyad" className="h-28 w-auto object-contain drop-shadow-lg" data-testid="login-hero-logo" />
          </div>
        </div>
        <div className="relative z-10 animate-fade-in">
          <blockquote className="text-white/95 text-3xl font-heading font-light leading-snug mb-4 tracking-tight">
            "Serving the community with transparency and trust."
          </blockquote>
          <p className="text-white/60 text-sm leading-relaxed">
            Managing memberships, contributions, and benefits — all in one place.
          </p>
        </div>
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-background lg:max-w-md lg:border-l lg:border-border">
        <div className="w-full max-w-sm animate-fade-in">
          {/* Mobile brand */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-11 h-11 bg-white rounded-lg border border-border flex items-center justify-center flex-shrink-0">
              <img src="/logo-icon.png" alt="Twenty20 Wariyad logo" className="w-9 h-9 object-contain" />
            </div>
            <div>
              <div className="text-foreground font-bold text-lg font-heading">Twenty20 Wariyad</div>
              <div className="text-muted-foreground text-xs uppercase tracking-[0.18em]">Charity Group</div>
            </div>
          </div>

          {/* Desktop logo above form */}
          <div className="hidden lg:flex justify-center mb-6">
            <img src="/logo-icon.png" alt="Twenty20 Wariyad logo" className="h-20 w-auto object-contain dark:bg-white dark:rounded-xl dark:p-2" />
          </div>

          <h2 className="text-3xl font-medium text-foreground mb-1 font-heading tracking-tight">Welcome back</h2>
          <p className="text-muted-foreground text-sm mb-8">Sign in to your account to continue</p>

          <form onSubmit={handleSubmit} data-testid={AUTH.loginForm} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-[0.15em] text-muted-foreground mb-1.5">Email Address</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid={AUTH.emailInput}
                className="w-full px-3 py-2.5 border border-input rounded-md text-sm text-foreground bg-card placeholder-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary transition-colors"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-[0.15em] text-muted-foreground mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  required
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  data-testid={AUTH.passwordInput}
                  className="w-full px-3 py-2.5 pr-10 border border-input rounded-md text-sm text-foreground bg-card placeholder-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-primary transition-colors"
                  placeholder="Enter password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  data-testid="toggle-password-visibility-btn"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/70 hover:text-foreground transition-colors"
                >
                  {showPw ? <EyeSlash size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                data-testid={AUTH.errorMessage}
                className="bg-destructive/10 border border-destructive/30 text-destructive text-sm px-3 py-2.5 rounded-md"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              data-testid={AUTH.submitButton}
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-2.5 px-4 rounded-md transition-colors duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : "Sign In"}
            </button>
          </form>

          <p className="text-xs text-muted-foreground/70 text-center mt-8">
            Twenty20 Charity Group Wariyad &copy; {new Date().getFullYear()}
          </p>
        </div>
      </div>
    </div>
  );
}
