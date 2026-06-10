import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatError } from "@/utils/api";
import { AUTH } from "@/constants/testIds";
import { ShieldStar, Eye, EyeSlash } from "@phosphor-icons/react";

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
    <div className="min-h-screen flex">
      {/* Left: Hero */}
      <div
        className="hidden lg:flex flex-1 flex-col justify-between p-12 relative"
        style={{
          backgroundImage: "url(https://images.pexels.com/photos/12518601/pexels-photo-12518601.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-stone-900/60" />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 backdrop-blur rounded-lg flex items-center justify-center">
              <ShieldStar size={24} weight="fill" color="white" />
            </div>
            <div>
              <div className="text-white font-bold text-xl font-heading">Twenty20</div>
              <div className="text-white/70 text-sm">Charity Group Wariyad</div>
            </div>
          </div>
        </div>
        <div className="relative z-10">
          <blockquote className="text-white/90 text-2xl font-heading font-semibold leading-snug mb-4">
            "Serving the community with transparency and trust."
          </blockquote>
          <p className="text-white/60 text-sm">
            Managing memberships, contributions, and benefits — all in one place.
          </p>
        </div>
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-stone-50 lg:max-w-md">
        <div className="w-full max-w-sm animate-fade-in">
          {/* Mobile brand */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 bg-green-800 rounded-lg flex items-center justify-center">
              <ShieldStar size={20} weight="fill" color="white" />
            </div>
            <div>
              <div className="text-stone-900 font-bold text-lg font-heading">Twenty20 Wariyad</div>
              <div className="text-stone-500 text-xs">Charity Group</div>
            </div>
          </div>

          <h2 className="text-2xl font-bold text-stone-900 mb-1 font-heading">Welcome back</h2>
          <p className="text-stone-500 text-sm mb-8">Sign in to your account to continue</p>

          <form onSubmit={handleSubmit} data-testid={AUTH.loginForm} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5">Email Address</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid={AUTH.emailInput}
                className="w-full px-3 py-2.5 border border-stone-300 rounded-md text-sm text-stone-900 bg-white placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700 transition-colors"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  required
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  data-testid={AUTH.passwordInput}
                  className="w-full px-3 py-2.5 pr-10 border border-stone-300 rounded-md text-sm text-stone-900 bg-white placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-green-700/30 focus:border-green-700 transition-colors"
                  placeholder="Enter password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                >
                  {showPw ? <EyeSlash size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                data-testid={AUTH.errorMessage}
                className="bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2.5 rounded-md"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              data-testid={AUTH.submitButton}
              className="w-full bg-green-800 hover:bg-green-900 text-white font-semibold py-2.5 px-4 rounded-md transition-colors duration-200 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : "Sign In"}
            </button>
          </form>

          <p className="text-xs text-stone-400 text-center mt-8">
            Twenty20 Charity Group Wariyad &copy; {new Date().getFullYear()}
          </p>
        </div>
      </div>
    </div>
  );
}
