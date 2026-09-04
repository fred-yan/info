import { NavLink } from 'react-router-dom';
import styles from './NavBar.module.css';

export default function NavBar() {
  return (
    <nav className={styles.navbar} aria-label="主导航">
      <ul className={styles.navList}>
        <li>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.active}` : styles.navLink
            }
          >
            热点快讯
          </NavLink>
        </li>
        <li>
          <NavLink
            to="/keywords"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.active}` : styles.navLink
            }
          >
            关键词榜
          </NavLink>
        </li>
        <li>
          <NavLink
            to="/platforms"
            className={({ isActive }) =>
              isActive ? `${styles.navLink} ${styles.active}` : styles.navLink
            }
          >
            平台状态
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}
