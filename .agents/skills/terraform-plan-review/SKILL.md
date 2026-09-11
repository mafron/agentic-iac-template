---
name: terraform-plan-review
description: Terraformのsaved plan、plan JSON、risk summary、OPA結果をレビューするときに使う。作成削除置換・IAM・公開範囲を確認し、productionやstate変更を人間へ引き渡す。fixtureと実AWS planを区別する。
---

# Terraform plan review

[root AGENTS](../../../AGENTS.md)、対象環境のAGENTS、
[production gate](../../../docs/production-gate.md) を読む。
このskillはplan/apply credentialの付与や承認を行わない。
Codexでは `$terraform-plan-review` または `/skills` から選択できる。

1. 入力がfixture、mock test、実AWS saved planのどれかを最初に明示する。
   実planでは対象commit、環境、account、region、backend/state key、plan roleを確認する。
   これらが不明なら推測でAWSへ接続しない。plan JSON自身のtagから環境を決めない。
2. 自分で作成する場合は、まず `make verify` と `make harness-status`。
   同梱のCodex coding設定はAWS credentialなし・network無効なので、保護されたplan runnerへ渡す。
   次の入口は、別途承認されたdev/stagingのplan roleを持つ実行経路で使う。

   ```bash
   make plan ENV=dev VAR_FILE=/absolute/private/dev.tfvars BACKEND_CONFIG=/absolute/private/dev.s3.hcl
   ```

   wrapperがsaved plan、JSON、risk、policy、manifestを生成する。
   productionの実planは通常agent hookから実行せず、保護されたplan runnerへ引き渡す。
3. 既存の信頼できるplan JSONをレビューする場合は以下を使う。
   実環境は実行経路から独立して指定し、提供されたENV文字列だけを信頼しない。

   ```bash
   make risk-summary ENV=dev PLAN_JSON=/absolute/private/plan.json
   make policy ENV=dev PLAN_JSON=/absolute/private/plan.json
   ```

   risk-summaryは0=HIGH RISKなし、2=HIGH RISK、1=不正入力。
   make経由では非ゼロがmake自身の終了コードに変わるため、要約とエラーメッセージを確認する。
   riskで停止しても、既存JSONのpolicy評価は別途行い、両結果を記録する。
4. create / update / delete / replaceの排他的な件数、IAM、SG、CIDR、public exposure、
   network、unknown security値、state操作、production影響を確認する。
   要約だけでなく該当resourceの差分と依存先を見る。policy PASSはapply承認ではない。
5. destroy、replacement、IAM/SG/CIDR、backend/state等の高リスクは、人間へ理由と影響を渡す。
   productionで自律的に続けず、[state例外手順](../../../docs/state-safety.md) を通常作業と分離する。
6. PRには機密を除いた要約と実行結果を示す。raw plan/stateは保護された保管先へ置く。
   人間が同一saved planとmanifestを確認し、別主体のapply roleで実行する。
   planの再生成・差替え・driftは再承認が必要。Agent自身はproduction applyしない。

実planが取得できない場合は未実行と報告する。fixtureの安全判定、read-only MCPの情報、
検証記録、skillを読んだ事実を、実環境への適用許可として使わない。
