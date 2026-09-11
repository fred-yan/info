import { useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import styles from './BottomSheet.module.css';

interface BottomSheetProps {
  /** 是否展开 */
  open: boolean;
  /** 标题文本 */
  title: string;
  /** 关闭回调 */
  onClose: () => void;
  children: React.ReactNode;
}

/**
 * 底部抽屉组件（Bottom Sheet）。
 * 通过 portal 挂在 body，不受父级 overflow 影响。
 * 点击遮罩或按 ESC 关闭。
 */
export function BottomSheet({ open, title, onClose, children }: BottomSheetProps) {
  const bodyRef = useRef<HTMLDivElement>(null);

  // ESC 关闭
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener('keydown', handleKey);
    // 打开时禁止背景滚动
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = prev;
    };
  }, [open, handleKey]);

  // 每次打开新关键词时滚到顶部
  useEffect(() => {
    if (open && bodyRef.current) {
      bodyRef.current.scrollTop = 0;
    }
  }, [open, title]);

  if (!open) return null;

  return createPortal(
    <>
      {/* 遮罩 */}
      <div
        className={styles.backdrop}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* 面板 */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={styles.sheet}
      >
        {/* 拖拽把手（纯装饰） */}
        <div className={styles.handle} aria-hidden="true">
          <div className={styles.handleBar} />
        </div>

        {/* 标题栏 */}
        <div className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {/* 内容区（可滚动） */}
        <div className={styles.body} ref={bodyRef}>
          {children}
        </div>
      </div>
    </>,
    document.body,
  );
}

export default BottomSheet;
