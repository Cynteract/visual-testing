import { getAuth, signInWithEmailAndPassword } from "firebase/auth";
import { deleteDoc, doc, getDoc, getFirestore } from "firebase/firestore";

import { strict as assert } from "assert";
import { initializeApp } from "firebase/app";
import { argv } from "process";

const args = argv.slice(2);
const parsedArgs = args.reduce(
  (acc, arg) => {
    const [key, value] = arg.split("=");
    acc[key] = value || true;
    return acc;
  },
  {} as Record<string, string | boolean>,
);

const database = parsedArgs["--database"];
assert.ok(database, "Expected --database to be provided");

let firebaseConfig;
if (database === "production") {
  firebaseConfig = {
    apiKey: "AIzaSyCXwvVgRV8P4JQZCumLOGudlZ6RzuBpfZw",
    authDomain: "cynteract-a52e4.firebaseapp.com",
    databaseURL: "https://cynteract-a52e4-default-rtdb.firebaseio.com",
    projectId: "cynteract-a52e4",
    storageBucket: "cynteract-a52e4.firebasestorage.app",
    messagingSenderId: "399891306750",
    appId: "1:399891306750:web:7a35d5d2f9dafe4176adaf",
    measurementId: "G-5C0BG3Z7SY",
  };
} else if (database === "testing") {
  firebaseConfig = {
    apiKey: "AIzaSyCrahmamqIadPhhp1bPkv4YxZBfnA4uCG0",
    authDomain: "cynteract-test.firebaseapp.com",
    projectId: "cynteract-test",
    storageBucket: "cynteract-test.firebasestorage.app",
    messagingSenderId: "348270652068",
    appId: "1:348270652068:web:c148bbb0708866df739431",
    measurementId: "G-98MZHXVBKQ",
  };
} else {
  throw new Error("Expected --database to be either 'production' or 'testing'");
}

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const username = parsedArgs["--username"] as string;
const password = parsedArgs["--password"] as string;
assert.ok(username, "Expected --username to be provided");
assert.ok(password, "Expected --password to be provided");
const auth = getAuth(app);
const login = await signInWithEmailAndPassword(auth, username, password);
const playerDoc = doc(db, "Player", login.user.uid);

if (parsedArgs["--resetPlayerData"] === true) {
  console.log("Reset player data.");
  await deleteDoc(playerDoc);
} else {
  console.log("Print player data.");
  const docSnap = await getDoc(playerDoc);
  console.log("Document data:", docSnap.data());
}

await auth.signOut();
