import './Pagination.css';

interface PaginationProps {
  page: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, hasNext, onPageChange }: PaginationProps) {
  return (
    <nav className="pagination" aria-label="分页导航">
      <button
        className="pagination__btn"
        disabled={page === 1}
        onClick={() => onPageChange(page - 1)}
        aria-label="上一页"
      >
        上一页
      </button>
      <span className="pagination__current" aria-current="page">
        {page}
      </span>
      <button
        className="pagination__btn"
        disabled={!hasNext}
        onClick={() => onPageChange(page + 1)}
        aria-label="下一页"
      >
        下一页
      </button>
    </nav>
  );
}

export default Pagination;
