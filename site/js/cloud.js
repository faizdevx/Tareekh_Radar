// Firebase Auth + Firestore wrapper. Loaded lazily; the site works without it (diary stays on the device).
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged, GoogleAuthProvider, signInWithPopup, createUserWithEmailAndPassword,
  signInWithEmailAndPassword, sendEmailVerification, sendPasswordResetEmail, signOut, deleteUser } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, collection, doc, getDocs, setDoc, deleteDoc, writeBatch } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
const db = getFirestore(app);
const col = (uid) => collection(db, "users", uid, "cases");

export const watch = (cb) => onAuthStateChanged(auth, cb);
export const signInGoogle = () => signInWithPopup(auth, new GoogleAuthProvider());
export const signIn = (email, pw) => signInWithEmailAndPassword(auth, email, pw);
export async function signUp(email, pw) {
  const c = await createUserWithEmailAndPassword(auth, email, pw);
  await sendEmailVerification(c.user);
  return c.user;
}
export const resendVerification = () => sendEmailVerification(auth.currentUser);
export const resetPassword = (email) => sendPasswordResetEmail(auth, email);
export const logout = () => signOut(auth);
export async function refreshUser() { await auth.currentUser.reload(); return auth.currentUser; }

export async function pull(uid) { return (await getDocs(col(uid))).docs.map((d) => ({ id: d.id, ...d.data() })); }
// Only the fields the security rules allow; the case id is the document id.
export const putCase = (uid, c) => setDoc(doc(db, "users", uid, "cases", c.id), {
  label: c.label, cnr: c.cnr, s: c.s, d: c.d, c: c.c, filed: c.filed, court: c.court, entries: c.entries, updated: c.updated });
export const removeCase = (uid, id) => deleteDoc(doc(db, "users", uid, "cases", id));

// shortcut: one batch (max 500 docs), the app caps a diary at 200 cases; upgrade if that cap grows.
export async function deleteAccount() {
  const u = auth.currentUser;
  const snap = await getDocs(col(u.uid));
  const b = writeBatch(db);
  snap.docs.forEach((d) => b.delete(d.ref));
  await b.commit();
  await deleteUser(u);
}
