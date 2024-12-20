const child_process = require('child_process');

child_process.execFileSync(
  'npm',
  ['install', '-g', 'rust-just'],
  { stdio: 'inherit' }
);
