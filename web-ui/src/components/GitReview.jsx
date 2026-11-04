export function GitReview({ open, status, diff, onClose }) {
  if (!open) return null;
  return <section class="diff-panel" role="dialog" aria-modal="true" aria-labelledby="diffTitle"><div class="diff-header"><div><div class="section-caption">REPOSITORY REVIEW</div><h2 id="diffTitle">Git status & diff</h2></div><button class="icon-button" onClick={onClose} aria-label="Đóng">×</button></div><h3>Git status</h3><pre class="code-block">{status}</pre><h3>Thay đổi</h3><pre class="code-block">{diff}</pre></section>;
}
