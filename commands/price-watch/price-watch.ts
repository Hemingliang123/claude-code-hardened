import type { LocalCommandCall, LocalCommandResult } from '../../types/command.js'
import { execFileNoThrow } from '../../utils/execFileNoThrow.js'
import { tryParseShellCommand } from '../../utils/bash/shellQuote.js'

const USAGE = [
  'Usage:',
  '  /price-watch collect --keyword "蓝牙耳机" --mode sample',
  '  /price-watch collect --keyword "机械键盘" --mode live',
  '  /price-watch --help',
  '',
  'Notes:',
  '  - `/price-watch` wraps `python3 -m price_watch_tool`.',
  '  - `serve` starts a long-running web server and is not exposed via this slash command.',
].join('\n')

function buildResult(stdout: string, stderr: string, code: number): LocalCommandResult {
  const parts = [stdout.trim(), stderr.trim()].filter(Boolean)
  if (parts.length === 0) {
    parts.push(code === 0 ? 'price-watch finished with no output' : `price-watch failed with exit code ${code}`)
  }
  if (code !== 0) {
    parts.unshift(`price-watch failed with exit code ${code}`)
  }
  return { type: 'text', value: parts.join('\n\n') }
}

function parseArgs(args: string): { ok: true; argv: string[] } | { ok: false; message: string } {
  if (!args.trim()) {
    return { ok: true, argv: ['--help'] }
  }
  const parsed = tryParseShellCommand(args)
  if (!parsed.success) {
    return { ok: false, message: `无法解析参数: ${parsed.error}\n\n${USAGE}` }
  }

  const argv: string[] = []
  for (const token of parsed.tokens) {
    if (typeof token !== 'string') {
      return {
        ok: false,
        message: `仅支持普通字符串参数，不支持 shell 操作符或特殊展开。\n\n${USAGE}`,
      }
    }
    argv.push(token)
  }
  return { ok: true, argv }
}

export const call: LocalCommandCall = async (
  args: string,
): Promise<LocalCommandResult> => {
  const parsed = parseArgs(args)
  if (!parsed.ok) {
    return { type: 'text', value: parsed.message }
  }

  if (parsed.argv[0] === 'serve') {
    return {
      type: 'text',
      value: [
        '`serve` 会启动长时间运行的本地 Web 服务，不适合通过 slash command 挂起当前会话。',
        '请改用终端执行：',
        'python3 -m price_watch_tool serve --host 127.0.0.1 --port 8765',
      ].join('\n'),
    }
  }

  const result = await execFileNoThrow(
    'python3',
    ['-m', 'price_watch_tool', ...parsed.argv],
    {
      timeout: 2 * 60 * 1000,
      preserveOutputOnError: true,
      useCwd: true,
    },
  )

  return buildResult(result.stdout, result.stderr, result.code)
}
