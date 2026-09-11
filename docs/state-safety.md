# State safety / break-glass

通常のAgentは `.tfstate` / backupを直接編集しない。`state rm`、`state mv`、
`force-unlock`、`destroy` を実行しない。`terraform import`、import / moved / removed blockも
別のstate変更Issueと人間の承認に分離する。宣言的なmovedも安全審査が不要になるわけではない。
wrapperはこれらの入口を持たず、plan中のimport / address移動 / forgetをpolicyで拒否する。

backendは3環境それぞれS3を宣言するが、bucket作成やstate移行はこのworkloadで行わない。
`.s3.hcl.example` は実行用ではない。空のbackendでplanしたりlocal stateにフォールバックしない。
通常initに `-reconfigure` / `-migrate-state` は渡さない。backend不一致は停止理由になる。

実運用では別AWS accountまたは少なくともbucket/keyごとに権限を分け、暗号化、TLS、
public access block、versioning、auditを有効にし、S3 lockfileによる排他制御を使う。
Agentにstateのwrite/deleteを付与しない。planにはstate readとlock objectへの限定的なwrite/deleteが
必要になる。lock objectだけの権限をstate本体のwrite権限に広げない。
stateのreadにもsecret流出リスクがあるため、plan runnerへのアクセスを限定する。

例外作業は次の順で、人間のstate管理担当者が実施する。

1. 変更ticket、対象account/backend/key/workspace、対象address、理由、担当者・承認者を確定。
2. apply runnerを停止し、ロック保有者と他の実行がないことを確認。
3. 暗号化されアクセス制御された場所にstateのversion/backupと復旧手順を確保。gitへ置かない。
4. 別の短命break-glass roleで最小の操作を実施し監査記録を残す。
5. fresh planで意図しないcreate/deleteがないこと、実リソースとの整合を確認。
6. 必要な適用は別途承認し、権限を失効させる。

importは実リソースを新規作成しないがstateとの対応を変更する。wrong addressへのimportは
次回planの削除や再作成につながり得るため、通常のfeature変更と混ぜない。
force-unlockはtimeout解消の定型手順にしない。live writer不在の証拠を得てから人間が判断する。
