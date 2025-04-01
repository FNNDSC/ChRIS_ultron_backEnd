const child_process = require('child_process');

child_process.execFileSync(
  'pipx',
  ['install', 'rust-just'],
  { stdio: 'inherit' }
);
