import { createServer } from "vite";
import fs from "fs";

async function runTests() {
  console.log("=== SUPABASE FRONTEND FOUNDATION TESTS ===\n");

  // Test 1: Successful Initialization with environment
  console.log("Test 1: Valid initialization via import.meta.env...");
  const server = await createServer({
    root: ".",
    server: { middlewareMode: true },
  });

  const mod = await server.ssrLoadModule("/src/lib/supabase.ts");
  if (!mod.supabase || typeof mod.supabase !== "object") {
    throw new Error("supabase client export is missing or not an object");
  }
  if (!mod.supabase.auth || typeof mod.supabase.auth !== "object") {
    throw new Error("supabase.auth is missing or not an object");
  }
  const session = await mod.supabase.auth.getSession();
  console.log("  [PASS] supabase instance created and auth.getSession() succeeded:", session.data ? "OK" : "No session");
  await server.close();

  // Test 2: Missing VITE_SUPABASE_URL
  console.log("\nTest 2: Missing VITE_SUPABASE_URL validation...");
  const testKey = "sb_publishable_secret_test_key_12345";
  const serverMissingUrl = await createServer({
    root: ".",
    server: { middlewareMode: true },
    define: {
      "import.meta.env.VITE_SUPABASE_URL": JSON.stringify(""),
      "import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY": JSON.stringify(testKey),
    },
  });

  let errorUrl = null;
  try {
    await serverMissingUrl.ssrLoadModule("/src/lib/supabase.ts");
  } catch (err) {
    errorUrl = err;
  } finally {
    await serverMissingUrl.close();
  }

  if (!errorUrl) {
    throw new Error("Expected missing VITE_SUPABASE_URL to throw, but it succeeded");
  }
  if (!errorUrl.message.includes("VITE_SUPABASE_URL is not set")) {
    throw new Error(`Unexpected error message: ${errorUrl.message}`);
  }
  if (errorUrl.message.includes(testKey)) {
    throw new Error("Security failure: publishable key was exposed in error message!");
  }
  console.log("  [PASS] Missing URL threw expected error without leaking key:", errorUrl.message.split("\n")[0]);

  // Test 3: Missing VITE_SUPABASE_PUBLISHABLE_KEY
  console.log("\nTest 3: Missing VITE_SUPABASE_PUBLISHABLE_KEY validation...");
  const testUrl = "https://my-test-project.supabase.co";
  const serverMissingKey = await createServer({
    root: ".",
    server: { middlewareMode: true },
    define: {
      "import.meta.env.VITE_SUPABASE_URL": JSON.stringify(testUrl),
      "import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY": JSON.stringify(""),
    },
  });

  let errorKey = null;
  try {
    await serverMissingKey.ssrLoadModule("/src/lib/supabase.ts");
  } catch (err) {
    errorKey = err;
  } finally {
    await serverMissingKey.close();
  }

  if (!errorKey) {
    throw new Error("Expected missing VITE_SUPABASE_PUBLISHABLE_KEY to throw, but it succeeded");
  }
  if (!errorKey.message.includes("VITE_SUPABASE_PUBLISHABLE_KEY is not set")) {
    throw new Error(`Unexpected error message: ${errorKey.message}`);
  }
  console.log("  [PASS] Missing Key threw expected error without leaking secrets:", errorKey.message.split("\n")[0]);

  // Test 4: Secret and database connection leakage check
  console.log("\nTest 4: Checking frontend code and configs for leaked database URLs/secrets...");
  const envContent = fs.readFileSync(".env.local", "utf8");
  if (envContent.includes("postgres://") || envContent.includes("postgresql://") || envContent.includes("5432")) {
    throw new Error("Security failure: Database connection string found in frontend .env.local!");
  }
  const libContent = fs.readFileSync("src/lib/supabase.ts", "utf8");
  if (libContent.includes("postgres://") || libContent.includes("postgresql://")) {
    throw new Error("Security failure: Database connection string found in supabase.ts!");
  }
  console.log("  [PASS] No database credentials or server secrets found in frontend.");

  console.log("\nALL SUPABASE FOUNDATION TESTS PASSED SUCCESSFULLY!");
}

runTests().catch((err) => {
  console.error("\nTEST SUITE FAILED:", err);
  process.exit(1);
});
