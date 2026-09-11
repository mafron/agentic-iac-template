# Codexで使う

このリポジトリの主な接続先はCodex CLI / IDEです。通常のcoding sessionではAWS credentialを使わず、
Terraform変更、mock test、検証済み差分のレビューまでを担当します。実planは保護されたrunner、
production applyは人間が承認した別主体へ渡します。

## 初回セットアップ

Linux / macOS / WSLのBash環境を想定します。native Windowsの接続は未検証です。
project hooks対応のCodexと [固定版toolchain](toolchain.md) を導入します。
Codexの確認対象は2026-09-11時点の公式仕様です。古いclientが設定を認識しない場合は、
hookなしの実行を有効な接続と見なさず、clientの対応状況を確認してください。

1. cloneのルートで `AGENTS.md`、`.codex/`、`scripts/agent_hook.py`、`scripts/harness.py` をレビューします。
2. 通常のterminalで `make verify` を実行します。初回provider/plugin取得には通信が必要です。
   Codex設定のnetworkを恒常的に開放する必要はありません。
3. `make hooks-install` でこのcloneのGit hooksを有効にします。既存の別hook設定は上書きしません。
4. repoルートを開いてCodexを起動し、レビューしたprojectを信頼します。
   `/hooks` でPreToolUse / PostToolUse / Stopの定義を確認・信頼します。
   未信頼・変更されたhook定義は警告とともに実行対象から外れるため、登録・trust状態を確認してください。
5. 通常terminalで `make codex-check` を実行し、実CLIによるnative rulesの禁止判定を確認します。
   Codex CLIがなければ非ゼロ終了します。IDEの接続確認とは別の検査です。
6. `/skills` または `$terraform-change` を指定して変更を依頼します。

例: 「`$terraform-change` application moduleのtagに関するmock assertionを追加し、make verifyまで実行してください。」
saved planのレビューは `$terraform-plan-review` を使います。skillは作業手順であり、実行権限を付与しません。

hookのtrustは**定義のhash**に対するものです。定義を変更したら再確認します。
呼び出されるscriptの内容まで認証する仕組みではないので、CODEOWNERSとrequired reviewも設定します。
hook trustのbypassオプションは使用しません。既存のuser-level hookも実行され得るため、
同じ定義をuser設定やinline設定へ重複コピーせず、`/hooks` で実際の構成を確認します。

## 設定の役割

| File | 効果と境界 |
|---|---|
| `.codex/config.toml` | `workspace-write`、network無効、on-request approval。AWS/TF token環境変数を除き、AWS profile file/metadata取得も既定では無効化 |
| `.codex/hooks.json` | Bash / apply_patch前の共通gate、patch後のfmt feedback、完了時の検証記録チェック |
| `.codex/rules/terraform.rules` | sandbox外へ実行を要求するraw `terraform` / `aws` commandを禁止。広いallow規則は追加しない |
| `.agents/skills/` | Codexが検出するTerraform変更・planレビューの手順 |
| `.githooks/` + CI | clientとは独立したcommit / push / PR検証 |

`.rules` はexperimentalなcommand prefix判定であり、全shell実行やfile編集を統制するsandboxではありません。
例えば `terraform -chdir=environments/prod apply` はraw Terraformの禁止に含めますが、
make wrapper内部のsubprocessを1つずつこのruleで検査する設計ではありません。
wrapperとhook script自体をレビューし、実AWSの権限は別主体に置きます。

環境変数filterは一般的なsecret隔離の証明ではありません。disk上のcredential、別のMCP、
別profile、対象外toolも含めた境界は実行基盤で設定します。このrepoは個人のCodex設定や
既存credentialを変更せず、modelや有料サービスも固定しません。

## 接続確認

`make python-test` はJSON入出力契約と設定に記載したcommandの起動を検証します。
実Codexセッションでhookが発火したことは、このtestだけでは証明できません。
導入者は使い捨てcloneで次を確認します。

- 許可したsource readとapplicationのpatchが通り、patch後にfmt feedbackが返る。
- productionを含む複数file patch、保護pathへのmove、raw applyがPreToolUseで拒否される。
- 未実行・古いverify記録ならStopが一度修正を要求し、続けて失敗する場合はFAILを報告する。
- tool欠如・timeoutをPASSと扱わず、`make verify` 成功後だけ `make harness-status` がPASSになる。

詳細なallowlist、payload、対象外tool、Git gateの限界は [Hooksとskills](hooks-and-skills.md) を参照してください。
Claude向け接続例はCodex設定に置き換えています。既存のローカルClaude設定は自動削除しません。
他clientでは共通Make/Git/skillsを使い、それぞれの公式仕様に合わせたadapterを用意します。

## 公式仕様と判断の記録

確認日: 2026-09-11。native Codex CLIのversion/実セッションはこの作成環境では未確認です。

- [Hooks](https://learn.chatgpt.com/docs/hooks): project hooks、trust、canonical tool名とpayloadを採用。
- [Skills](https://learn.chatgpt.com/docs/build-skills): `.agents/skills` を維持し、明示的な選択をREADMEへ追加。
- [Config reference](https://learn.chatgpt.com/docs/config-file/config-reference): 通常coding用のsandboxと環境変数設定を採用。
- [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules): native ruleは補助とし、実CLI検査を任意の入口へ分離。

client更新時はこれらの仕様、adapterの回帰test、実セッションの確認を一緒に見直します。
