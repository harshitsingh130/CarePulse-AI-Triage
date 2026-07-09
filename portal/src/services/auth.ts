/**
 * Cognito authentication using amazon-cognito-identity-js.
 * This library handles the SRP protocol and Cognito API calls properly
 * (no CORS issues — uses the Cognito SDK internally).
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  ISignUpResult,
} from 'amazon-cognito-identity-js';

const USER_POOL_ID = import.meta.env.VITE_USER_POOL_ID || 'us-west-2_fT2kDGhLX';
const CLIENT_ID = import.meta.env.VITE_USER_POOL_CLIENT_ID || '7asq0c1q14q1l6mne6clt3fpkp';

const userPool = new CognitoUserPool({
  UserPoolId: USER_POOL_ID,
  ClientId: CLIENT_ID,
});

export interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
}

class AuthService {
  private cognitoUser: CognitoUser | null = null;

  isAuthenticated(): boolean {
    const token = sessionStorage.getItem('accessToken');
    if (!token) return false;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }

  getAccessToken(): string | null {
    return sessionStorage.getItem('accessToken');
  }

  getUsername(): string | null {
    return sessionStorage.getItem('username');
  }

  /**
   * Get the user's Cognito groups from the ID token.
   */
  getUserGroups(): string[] {
    const idToken = sessionStorage.getItem('idToken');
    if (!idToken) return [];
    try {
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      return payload['cognito:groups'] || [];
    } catch {
      return [];
    }
  }

  /**
   * Check if user belongs to a clinical role (nurse, physician, admin).
   */
  isClinicalUser(): boolean {
    const groups = this.getUserGroups();
    return groups.some(g => ['nurse', 'physician', 'admin'].includes(g));
  }

  /**
   * Sign up a new user with email + password.
   */
  signUp(username: string, password: string, email: string, phone?: string): Promise<{ userConfirmed: boolean }> {
    const attributeList: CognitoUserAttribute[] = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
    ];

    if (phone) {
      attributeList.push(new CognitoUserAttribute({ Name: 'phone_number', Value: phone }));
    }

    return new Promise((resolve, reject) => {
      userPool.signUp(username, password, attributeList, [], (err, result) => {
        if (err) {
          reject(new Error(err.message || 'Sign up failed'));
          return;
        }
        sessionStorage.setItem('username', username);
        resolve({ userConfirmed: result?.userConfirmed ?? false });
      });
    });
  }

  /**
   * Confirm sign-up with verification code.
   */
  confirmSignUp(username: string, code: string): Promise<void> {
    const user = new CognitoUser({
      Username: username,
      Pool: userPool,
    });

    return new Promise((resolve, reject) => {
      user.confirmRegistration(code, true, (err, result) => {
        if (err) {
          reject(new Error(err.message || 'Confirmation failed'));
          return;
        }
        resolve();
      });
    });
  }

  /**
   * Resend confirmation code.
   */
  resendCode(username: string): Promise<void> {
    const user = new CognitoUser({
      Username: username,
      Pool: userPool,
    });

    return new Promise((resolve, reject) => {
      user.resendConfirmationCode((err, result) => {
        if (err) {
          reject(new Error(err.message || 'Failed to resend code'));
          return;
        }
        resolve();
      });
    });
  }

  /**
   * Sign in with username + password.
   */
  signIn(username: string, password: string): Promise<AuthTokens> {
    const user = new CognitoUser({
      Username: username,
      Pool: userPool,
    });
    this.cognitoUser = user;

    const authDetails = new AuthenticationDetails({
      Username: username,
      Password: password,
    });

    return new Promise((resolve, reject) => {
      user.authenticateUser(authDetails, {
        onSuccess: (session) => {
          const tokens: AuthTokens = {
            accessToken: session.getAccessToken().getJwtToken(),
            idToken: session.getIdToken().getJwtToken(),
            refreshToken: session.getRefreshToken().getToken(),
          };
          sessionStorage.setItem('accessToken', tokens.accessToken);
          sessionStorage.setItem('idToken', tokens.idToken);
          sessionStorage.setItem('refreshToken', tokens.refreshToken);
          sessionStorage.setItem('username', username);
          resolve(tokens);
        },
        onFailure: (err) => {
          if (err.code === 'UserNotConfirmedException') {
            reject(new Error('UserNotConfirmedException'));
          } else {
            reject(new Error(err.message || 'Sign in failed'));
          }
        },
        newPasswordRequired: (userAttributes) => {
          // Handle new password required (first-time login after admin creates user)
          reject(new Error('NEW_PASSWORD_REQUIRED'));
        },
        mfaRequired: (challengeName, challengeParameters) => {
          reject(new Error('MFA_REQUIRED'));
        },
      });
    });
  }

  /**
   * Sign out.
   */
  logout(): void {
    if (this.cognitoUser) {
      this.cognitoUser.signOut();
    }
    sessionStorage.removeItem('accessToken');
    sessionStorage.removeItem('idToken');
    sessionStorage.removeItem('refreshToken');
    sessionStorage.removeItem('username');
    this.cognitoUser = null;
  }
}

export const authService = new AuthService();
