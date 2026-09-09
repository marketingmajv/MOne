#!/usr/bin/env node
/**
 * M-One Anti-Monolith Watcher (scripts/monolith-watcher.js)
 * Monitora em tempo real arquivos do projeto M-One.
 * Emite alertas sonoros e notificações nativas do macOS/Windows caso arquivos ultrapassem o limite de linhas.
 */

const fs = require('fs');
const path = require('path');

let chokidar, notifier;
try {
  chokidar = require('chokidar');
  notifier = require('node-notifier');
} catch (e) {
  console.log('\x1b[33m[Aviso]\x1b[0m Módulos "chokidar" ou "node-notifier" não encontrados localmente.');
  console.log('Execute: npm install --no-save chokidar node-notifier');
  console.log('Ou utilize o watcher nativo em Python: python3 scripts/monolith_watcher.py\n');
}

const LINE_LIMIT = 500;
const BASE_DIR = path.resolve(__dirname, '..');

const WATCH_PATHS = [
  path.join(BASE_DIR, 'app.py'),
  path.join(BASE_DIR, 'database.py'),
  path.join(BASE_DIR, 'routes/**/*.py'),
  path.join(BASE_DIR, 'templates/**/*.html'),
  path.join(BASE_DIR, 'static/js/**/*.js')
];

console.log(`\x1b[36m[Anti-Monolith Watcher - M-One]\x1b[0m Iniciado! Observando arquivos (> ${LINE_LIMIT} linhas)...`);

function checkFile(filePath) {
  try {
    if (!fs.existsSync(filePath)) return;
    const stat = fs.statSync(filePath);
    if (!stat.isFile()) return;

    const content = fs.readFileSync(filePath, 'utf8');
    const lineCount = content.split('\n').length;

    if (lineCount > LINE_LIMIT) {
      const fileName = path.basename(filePath);
      const relPath = path.relative(BASE_DIR, filePath);

      // Alerta no terminal
      console.log(`\n\x1b[41m\x1b[37m ⚠️  ALERTA DE MONÓLITO M-ONE ⚠️  \x1b[0m`);
      console.log(`\x1b[31mO arquivo \x1b[1m${relPath}\x1b[0m\x1b[31m ultrapassou o limite estabelecido!\x1b[0m`);
      console.log(`Linhas atuais: \x1b[1m${lineCount}\x1b[0m / Limite: ${LINE_LIMIT}`);
      console.log(`\x1b[33mRecomendação: Ativar skill de Refatoração Proativa para modularizar em rotas/Blueprints.\x1b[0m\n`);

      // Notificação nativa no OS (Mac/Windows)
      if (notifier) {
        notifier.notify({
          title: '⚠️ M-One: Alerta de Monólito!',
          message: `O arquivo ${fileName} atingiu ${lineCount} linhas. Considere modularizar em Blueprints.`,
          sound: true,
          wait: false
        });
      }
    }
  } catch (error) {
    console.error(`\x1b[31m[Anti-Monolith Watcher] Erro ao analisar ${filePath}:\x1b[0m`, error.message);
  }
}

if (chokidar) {
  const watcher = chokidar.watch(WATCH_PATHS, {
    ignored: /(^|[\/\\])\../,
    persistent: true,
    ignoreInitial: false
  });

  watcher
    .on('add', filePath => checkFile(filePath))
    .on('change', filePath => checkFile(filePath));
} else {
  // Fallback sem chokidar: varredura direta uma vez
  console.log('Executando varredura estática de arquivos...');
  const filesToCheck = [
    path.join(BASE_DIR, 'app.py'),
    path.join(BASE_DIR, 'database.py')
  ];
  filesToCheck.forEach(checkFile);
}
