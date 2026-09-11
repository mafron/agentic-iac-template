## 目的・変更後の動作

<!-- Issue、変更理由、対象module/environment -->

## 検証

- [ ] `make verify` PASS（未実行やFAILは理由を記載）
- [ ] 固定Provider版の公式資料を確認し `docs/context/` に根拠を記録
- [ ] Mock / fixture / 実AWS plan のどれを確認したか明記

## Plan review

| environment / commit | create | update | delete | replace | policy |
|---|---:|---:|---:|---:|---|
| | | | | | |

- [ ] IAM / network / SG / public CIDR / KMS / database の差分を確認
- [ ] unknown security値、drift、state操作、backend差分を確認
- [ ] 高リスク変更の理由、影響、ロールバック案を記載
- [ ] production適用の承認は別途、対象saved planに紐付ける

<!-- 生のplan JSONやsecretを貼らない。適用承認者、監査記録へのアクセス制御済み参照を記載。 -->
