import { getAuth, signInWithEmailAndPassword } from "firebase/auth";
import {
  collection, deleteDoc, doc, getDoc, getDocsFromServer,
  getFirestore, Timestamp, writeBatch,
} from "firebase/firestore";
import type { DocumentReference } from "firebase/firestore";
import { readFileSync } from "fs";

import { strict as assert } from "assert";
import { initializeApp } from "firebase/app";
import { argv } from "process";

function restoreTypes(value: any): any {
  if (Array.isArray(value)) return value.map(restoreTypes);
  if (value && typeof value === "object") {
    if ("_seconds" in value && "_nanoseconds" in value) {
      return new Timestamp(value._seconds, value._nanoseconds);
    }
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, restoreTypes(item)]),
    );
  }
  return value;
}

async function restorePlayerFixture(player: DocumentReference) {
  const fixture = JSON.parse(readFileSync("fixtures/player.json", "utf8"));
  assert.equal(fixture.playerId, player.id, "Fixture belongs to a different account");
  for (const name of ["Trainings", "Mood"]) {
    assert.ok(Array.isArray(fixture[name]) && fixture[name].length > 0, `Missing ${name} fixture`);
    const ids = new Set();
    for (const record of fixture[name]) {
      assert.ok(typeof record.id === "string" && record.id && !record.id.includes("/"));
      assert.ok(record.data && typeof record.data === "object");
      assert.ok(!ids.has(record.id), `Duplicate ${name} document`);
      ids.add(record.id);
    }
  }

  const writes: { ref: DocumentReference; data: any }[] = [];
  const extras: DocumentReference[] = [];
  for (const name of ["Trainings", "Mood"]) {
    const history = collection(player, name);
    const expected = new Set(fixture[name].map((record: any) => record.id));
    const current = await getDocsFromServer(history);
    extras.push(...current.docs.filter(record => !expected.has(record.id)).map(record => record.ref));
    for (const record of fixture[name]) {
      writes.push({ ref: doc(history, record.id), data: restoreTypes(record.data) });
    }
  }

  // Restore the saved records before removing history added by previous runs.
  for (let i = 0; i < writes.length; i += 200) {
    const batch = writeBatch(player.firestore);
    for (const record of writes.slice(i, i + 200)) batch.set(record.ref, record.data);
    await batch.commit();
  }
  for (let i = 0; i < extras.length; i += 200) {
    const batch = writeBatch(player.firestore);
    for (const ref of extras.slice(i, i + 200)) batch.delete(ref);
    await batch.commit();
  }
  console.log(`Restored ${fixture.Trainings.length} trainings and ${fixture.Mood.length} moods.`);
}

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

if (parsedArgs["--restorePlayerData"] === true) {
  await restorePlayerFixture(playerDoc);
} else if (parsedArgs["--resetPlayerData"] === true) {
  console.log("Reset player data.");
  await deleteDoc(playerDoc);
} else {
  console.log("Print player data.");
  const docSnap = await getDoc(playerDoc);
  console.log("Document data:", docSnap.data());
}

await auth.signOut();
