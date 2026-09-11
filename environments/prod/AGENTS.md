# Production scope

ルートの指示に追加する。このrootへ伝播する共有moduleの変更にも適用する。

**production applyをAgent自身で実行してはいけない。**

以下を発見した場合は、影響・対象address・plan要約を提示して人間の判断を待つ。
許可されたread-only調査、ローカルMock検証、レビュー資料の作成は続けられるが、
破壊的変更の確定、迂回、実環境の変更を自律的に進めない。

- destroy / delete、replacement（create-before-destroyも含む）
- IAM / trust policy / 権限付与の変更
- security group / route / CIDR / subnet / AZ の変更
- backend / state / import / moved / removed / unlock の操作
- KMS / database の変更

`make plan ENV=prod ...` は変更ありならHIGH RISKで終了コード2、
policy denyなら非ゼロで止まる。`--fail-on-high-risk`やpolicyを外して通過させない。
これは人間の承認を機械的に再現する機能ではない。承認は `docs/production-gate.md` の外部手順に従う。
PRの承認と、特定のsaved planに対する実行承認を区別する。
今回の初期サンプル作成は依頼済みのコード作成であり、実productionの変更を意味しない。
