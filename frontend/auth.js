import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import {
    getAuth,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signInWithPopup,
    GoogleAuthProvider,
    onAuthStateChanged,
    signOut
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

const firebaseConfig = {
    apiKey: "AIzaSyAbTL7wsv9xe5MdAUt2MLKu1Ne6DM3CTLc",
    authDomain: "scm-b33b9.firebaseapp.com",
    projectId: "scm-b33b9",
    storageBucket: "scm-b33b9.firebasestorage.app",
    messagingSenderId: "718143619059",
    appId: "1:718143619059:web:78728e3fb157029134dc86",
    measurementId: "G-C9D1416NXE"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

// Global token variable to be used in script.js
window.firebaseAuthToken = null;

document.addEventListener('DOMContentLoaded', () => {
    const authContainer = document.getElementById('auth-container');
    const appContainer = document.getElementById('main-app-container');

    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('auth-email');
    const passwordInput = document.getElementById('auth-password');
    const authError = document.getElementById('auth-error');

    const googleLoginBtn = document.getElementById('google-login-btn');
    const toggleSignupBtn = document.getElementById('toggle-signup');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const authTitle = document.getElementById('auth-title');

    const signOutBtn = document.getElementById('sign-out-btn');

    let isSignupMode = false;

    // Listen for Auth State Changes
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            // User is signed in.
            authContainer.classList.add('hidden');
            appContainer.classList.remove('hidden');

            // Fetch token for backend requests
            window.firebaseAuthToken = await user.getIdToken();

            // Optionally, refresh token periodically if needed
        } else {
            // No user is signed in.
            authContainer.classList.remove('hidden');
            appContainer.classList.add('hidden');
            window.firebaseAuthToken = null;
        }
    });

    // Toggle between Login and Signup modes
    if (toggleSignupBtn) {
        toggleSignupBtn.addEventListener('click', (e) => {
            e.preventDefault();
            isSignupMode = !isSignupMode;
            if (isSignupMode) {
                authTitle.textContent = "Create an Account";
                authSubmitBtn.textContent = "Sign Up";
                toggleSignupBtn.textContent = "Already have an account? Log In";
            } else {
                authTitle.textContent = "Welcome Back";
                authSubmitBtn.textContent = "Log In";
                toggleSignupBtn.textContent = "Need an account? Sign Up";
            }
            authError.classList.add('hidden');
        });
    }

    // Handle Email/Password Login & Signup
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            authError.classList.add('hidden');

            const email = emailInput.value;
            const password = passwordInput.value;

            try {
                if (isSignupMode) {
                    await createUserWithEmailAndPassword(auth, email, password);
                } else {
                    await signInWithEmailAndPassword(auth, email, password);
                }
            } catch (error) {
                authError.textContent = error.message;
                authError.classList.remove('hidden');
            }
        });
    }

    // Handle Google Login
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', async () => {
            authError.classList.add('hidden');
            try {
                await signInWithPopup(auth, googleProvider);
            } catch (error) {
                authError.textContent = error.message;
                authError.classList.remove('hidden');
            }
        });
    }

    // Handle Sign Out
    if (signOutBtn) {
        signOutBtn.addEventListener('click', () => {
            signOut(auth).catch((error) => {
                console.error("Sign out error", error);
            });
        });
    }
});
