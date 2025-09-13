#!/usr/bin/env node

// Simple test script to verify the setup
const fs = require('fs');
const path = require('path');

console.log('🧪 Testing RxVoice Assistant Setup...\n');

const tests = [
  {
    name: 'Backend package.json exists',
    test: () => fs.existsSync(path.join(__dirname, 'backend', 'package.json'))
  },
  {
    name: 'Frontend package.json exists',
    test: () => fs.existsSync(path.join(__dirname, 'frontend', 'package.json'))
  },
  {
    name: 'Backend node_modules exists',
    test: () => fs.existsSync(path.join(__dirname, 'backend', 'node_modules'))
  },
  {
    name: 'Frontend node_modules exists',
    test: () => fs.existsSync(path.join(__dirname, 'frontend', 'node_modules'))
  },
  {
    name: 'Backend server.js exists',
    test: () => fs.existsSync(path.join(__dirname, 'backend', 'server.js'))
  },
  {
    name: 'Frontend App.js exists',
    test: () => fs.existsSync(path.join(__dirname, 'frontend', 'src', 'App.js'))
  },
  {
    name: 'Database directory exists',
    test: () => fs.existsSync(path.join(__dirname, 'database'))
  },
  {
    name: 'Backend .env file exists',
    test: () => fs.existsSync(path.join(__dirname, 'backend', '.env'))
  }
];

let passed = 0;
let failed = 0;

tests.forEach(test => {
  try {
    if (test.test()) {
      console.log(`✅ ${test.name}`);
      passed++;
    } else {
      console.log(`❌ ${test.name}`);
      failed++;
    }
  } catch (error) {
    console.log(`❌ ${test.name} - Error: ${error.message}`);
    failed++;
  }
});

console.log(`\n📊 Results: ${passed} passed, ${failed} failed`);

if (failed === 0) {
  console.log('\n🎉 All tests passed! Your setup looks good.');
  console.log('\n🚀 Next steps:');
  console.log('1. Edit backend/.env with your API keys');
  console.log('2. Start backend: cd backend && npm run dev');
  console.log('3. Start frontend: cd frontend && npm start');
} else {
  console.log('\n⚠️  Some tests failed. Please run the setup script:');
  console.log('   ./setup.sh');
}

// Check for API keys if .env exists
const envPath = path.join(__dirname, 'backend', '.env');
if (fs.existsSync(envPath)) {
  console.log('\n🔑 Checking API keys...');
  const envContent = fs.readFileSync(envPath, 'utf8');
  
  const requiredKeys = ['DEEPGRAM_API_KEY', 'GEMINI_API_KEY', 'ELEVENLABS_API_KEY'];
  const missingKeys = [];
  
  requiredKeys.forEach(key => {
    const regex = new RegExp(`${key}=(.+)`);
    const match = envContent.match(regex);
    if (!match || match[1].includes('your_') || match[1].trim() === '') {
      missingKeys.push(key);
    }
  });
  
  if (missingKeys.length === 0) {
    console.log('✅ All API keys appear to be configured');
  } else {
    console.log(`⚠️  Missing or placeholder API keys: ${missingKeys.join(', ')}`);
    console.log('   Please update backend/.env with your actual API keys');
  }
}

