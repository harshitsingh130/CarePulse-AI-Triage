/**
 * Authentication Page — Sign Up / Sign In with Cognito.
 * Supports: sign-up with verification code, sign-in with password.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/services/auth';

type AuthMode = 'signin' | 'signup' | 'confirm' | 'challenge';

export function Auth({ onLogin }: { onLogin?: () => void }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>('signin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [challengeSession, setChallengeSession] = useState('');
  const [challengeName, setChallengeName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await authService.signIn(username, password);
      if ('challengeName' in result) {
        setChallengeSession(result.session);
        setChallengeName(result.challengeName);
        setMode('challenge');
      } else {
        onLogin?.();
        const params = new URLSearchParams(window.location.search);
        const redirect = params.get('redirect');
        navigate(redirect || '/');
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sign in failed';
      if (msg.includes('not confirmed') || msg.includes('UserNotConfirmedException')) {
        setMessage('Your account needs verification. Enter the code sent to your email/phone.');
        setMode('confirm');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await authService.signUp(
        username,
        password,
        email || undefined,
        phone || undefined,
      );
      if (result.userConfirmed) {
        setMessage('Account created! You can sign in now.');
        setMode('signin');
      } else {
        setMessage('A verification code has been sent. Please check your email/phone.');
        setMode('confirm');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await authService.confirmSignUp(username, code);
      setMessage('Account verified! You can sign in now.');
      setMode('signin');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResendCode = async () => {
    try {
      await authService.resendCode(username);
      setMessage('A new code has been sent.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend code');
    }
  };

  const handleChallenge = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await authService.respondToChallenge(username, challengeName, code, challengeSession);
      onLogin?.(); navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Challenge failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>{mode === 'signup' ? 'Create Account' : mode === 'confirm' ? 'Verify Account' : mode === 'challenge' ? 'Verification' : 'Sign In'}</h1>
        <p className="auth-subtitle">
          {mode === 'signup' ? 'Register to use the triage system' :
           mode === 'confirm' ? 'Enter the verification code' :
           mode === 'challenge' ? `Enter the ${challengeName === 'SMS_MFA' ? 'SMS' : ''} code` :
           'Access your health records'}
        </p>

        {message && <p className="auth-message">{message}</p>}
        {error && <p className="error-message" role="alert">{error}</p>}

        {/* Sign In Form */}
        {mode === 'signin' && (
          <form onSubmit={handleSignIn}>
            <label htmlFor="username" className="auth-label">Username or Email</label>
            <input
              id="username"
              type="text"
              className="auth-input"
              placeholder="Enter your email or username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />

            <label htmlFor="password" className="auth-label">Password</label>
            <input
              id="password"
              type="password"
              className="auth-input"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>

            <p className="auth-switch">
              Don&apos;t have an account?{' '}
              <button type="button" className="auth-link" onClick={() => { setMode('signup'); setError(null); setMessage(null); }}>
                Sign Up
              </button>
            </p>
          </form>
        )}

        {/* Sign Up Form */}
        {mode === 'signup' && (
          <form onSubmit={handleSignUp}>
            <label htmlFor="signup-username" className="auth-label">Username</label>
            <input
              id="signup-username"
              type="text"
              className="auth-input"
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />

            <label htmlFor="signup-email" className="auth-label">Email</label>
            <input
              id="signup-email"
              type="email"
              className="auth-input"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />

            <label htmlFor="signup-phone" className="auth-label">Phone (optional)</label>
            <input
              id="signup-phone"
              type="tel"
              className="auth-input"
              placeholder="+1234567890"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />

            <label htmlFor="signup-password" className="auth-label">Password</label>
            <input
              id="signup-password"
              type="password"
              className="auth-input"
              placeholder="Min 12 chars, uppercase, lowercase, digits"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={12}
            />

            <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
              {loading ? 'Creating account...' : 'Sign Up'}
            </button>

            <p className="auth-switch">
              Already have an account?{' '}
              <button type="button" className="auth-link" onClick={() => { setMode('signin'); setError(null); setMessage(null); }}>
                Sign In
              </button>
            </p>
          </form>
        )}

        {/* Confirmation Code Form */}
        {mode === 'confirm' && (
          <form onSubmit={handleConfirm}>
            <label htmlFor="confirm-code" className="auth-label">Verification Code</label>
            <input
              id="confirm-code"
              type="text"
              className="auth-input auth-input--otp"
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              required
              autoFocus
            />

            <button type="submit" className="btn btn--primary btn--full" disabled={loading || code.length < 6}>
              {loading ? 'Verifying...' : 'Verify'}
            </button>

            <button type="button" className="auth-link" onClick={handleResendCode}>
              Resend code
            </button>
          </form>
        )}

        {/* Challenge Form (MFA) */}
        {mode === 'challenge' && (
          <form onSubmit={handleChallenge}>
            <label htmlFor="challenge-code" className="auth-label">Code</label>
            <input
              id="challenge-code"
              type="text"
              className="auth-input auth-input--otp"
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6}
              required
              autoFocus
            />

            <button type="submit" className="btn btn--primary btn--full" disabled={loading || code.length < 6}>
              {loading ? 'Verifying...' : 'Submit'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
