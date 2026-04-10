import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogIn, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const result = await login(email, password);
      if (result.success) {
        navigate('/');
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      {/* Decorative background blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-primary/20 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-brand-secondary/20 rounded-full blur-[100px] pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="auth-card"
      >
        <div className="flex flex-col items-center mb-8">
          <div className="bg-clip-text text-transparent bg-gradient-to-r from-brand-primary to-brand-secondary font-outfit text-5xl font-extrabold tracking-tight">Aura</div>
          <h2 className="mt-4 text-2xl font-semibold text-text-primary">Welcome back</h2>
          <p className="text-text-secondary mt-2">Log in to your account to continue</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">

          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-xs font-medium text-text-secondary ml-1">Email Address</label>
            <input
              id="email"
              type="email"
              className="w-full bg-black/20 border border-white/5 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all text-sm placeholder:text-text-tertiary"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center ml-1">
              <label htmlFor="password" className="text-xs font-medium text-text-secondary">Password</label>
            </div>
            <input
              id="password"
              type="password"
              className="w-full bg-black/20 border border-white/5 rounded-xl px-4 py-3.5 text-white focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary transition-all text-sm placeholder:text-text-tertiary"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            className="w-full btn-premium mt-4 py-3.5"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="w-5 h-5 animate-spin mx-auto" />
            ) : (
              <div className="flex items-center justify-center gap-2">
                <LogIn size={18} />
                <span>Log in</span>
              </div>
            )}
          </button>
        </form>

        <div className="mt-8 text-center text-sm text-text-secondary">
          Don't have an account? <Link to="/signup" className="text-brand-primary hover:text-brand-secondary font-medium transition-colors ml-1">Sign up</Link>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;
