const child_process = require('child_process');

const CONTAINER_ENGINE = process.env.INPUT_ENGINE;
const JUST_COMMAND = process.env.INPUT_COMMAND;

const script = `
set -x
just prefer ${CONTAINER_ENGINE}
just ${JUST_COMMAND}
rc=$?
if [ "$rc" != '0' ]; then
  just logs
fi
exit $rc
`;

child_process.execFileSync('bash', ['-c', script], { stdio: 'inherit' });

