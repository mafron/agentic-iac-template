# Production Human Gate

このリポジトリはapplyを実装しない。Agentが編集できる文書・scriptだけを安全境界にせず、
人間が管理するGitHub / IAM / backend側の設定で実行を制御する。

導入時に人間の管理者が設定するもの:

1. mainの直接push / force pushを禁止し、required checkにTerraform Checkを指定。
2. 実teamに置換したCODEOWNERSとrequired code owner review、stale approval無効化、
   最新差分の別担当者レビューを設定。module / prod / policy / workflow / wrapper変更を対象にする。
3. `plan-dev` / `plan-staging` / `plan-prod` GitHub Environmentを先に作成し、
   selected deployment branchをdefault branchだけに制限。特にprodはrequired reviewer、
   self-review禁止、bypass禁止を組織要件に応じ設定。
4. plan用OIDC trustを該当repositoryとenvironmentの実際のsubject、audienceに完全一致させる。
   ワイルドカードで全branch / PR / environmentを許可しない。
5. apply roleはAgent / plan roleからAssumeRole不能にする。人間または別の保護された
   deployment基盤だけが短命credentialを得られるようにする。

GitHub Environment名をworkflowに書くだけではreviewerやbranch制限は設定されない。
またrequired reviewerなどの提供範囲はrepository visibilityと契約に依存する。
利用できない場合は、外部の承認システムまたはMFA付き人間の実行をgateとする。
ローカルのMock検証とOPAに有料サービスは要らない。

本サンプルの実plan workflowはreview済みdefault branchでのみ手動実行する。
PRでverify → 人間がcodeをレビューしてmerge → CIでreal plan / policy →
**そのplanに対する実行承認** → 別主体によるapply、の順序で運用できる。
merge前のreal planが必要なら、レビュー済みcommitを保護された実行基盤へ渡す方式を追加する。
未レビューPRのHCL / test / external data sourceをcredential付きrunnerに実行させない。

承認する証拠はcommit SHA、account・region・backend/key、tfvarsのhash、Terraform/provider版、
binary planとplan JSONのSHA256、risk summary、policy結果、変更理由と復旧案。
ローカルwrapperはmanifestのgit SHAだけではdirty treeの証明にならない。実行候補はclean checkoutから作る。
生成manifestは改ざん防止署名ではない。承認基盤が出所・保存先・権限を保護する。

`make plan ENV=prod` はすべてのmanaged変更をHIGH RISKとして終了コード2で止める。
prodのdelete/replacementはOPAでdenyする。承認済み例外は通常policyを緩めず、
別のbreak-glass手順と限定された例外審査で扱う。
plan実行前のEnvironment approvalはcredential利用承認であり、生成後の適用承認とは別。

apply主体は同一commit・入力・stateに対する承認済みsaved planだけを使う。
承認後にplanやコードが変わった場合、あるいはstate更新や時間経過でplanが古くなった場合は、
fresh planと再承認を行う。`terraform apply` に暗黙の再planを任せない。
apply後は結果・state更新・監査証跡を確認する。

現workflowは生planをartifactやPRコメントへ送らない。real planのレビューをCI runner外で
完結させるには、アクセス制御・暗号化・短期保管・hashによる同一性確認を備えた証拠保存先を追加する。
この未実装部分があるため、workflow成功だけでproduction導入完了とはならない。

参考:

- [GitHub OIDC in AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [GitHub Environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
