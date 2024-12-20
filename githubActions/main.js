const child_process = require('child_process');

const CONTAINER_ENGINE = process.env.INPUT_ENGINE;
const JUST_COMMAND = process.env.INPUT_COMMAND;

const script = `
set -x
cd ${__dirname}/..
just prefer ${CONTAINER_ENGINE}

# start-up is being retried as a workaround for
# https://github.com/FNNDSC/ChRIS_ultron_backEnd/issues/573
for i in {1..5}; do
  just start-ancillary && start=good && break
  echo "::warning ::Ancillary services failed to start. Attempt=$i"
done

if [ "$start" != "good" ]; then
  echo "::error ::Failed to start ancillary services."
  exit 1
fi

just ${JUST_COMMAND}
rc=$?
if [ "$rc" != '0' ]; then
  just logs
fi
exit $rc
`;

child_process.execFileSync('bash', ['-c', script], { stdio: 'inherit' });

