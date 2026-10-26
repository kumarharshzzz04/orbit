// ORBIT Frontend - Button Component
// Reusable button with multiple variants

import { forwardRef, ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      loading = false,
      fullWidth = false,
      disabled,
      className = '',
      ...props
    },
    ref
  ) => {
    const baseClasses =
      'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors duration-150 focus-ring disabled:opacity-50 disabled:cursor-not-allowed';

    const variantClasses = {
      primary: 'bg-orbit-accent-primary text-orbit-text-inverse hover:bg-cyan-500 active:bg-cyan-600',
      secondary: 'bg-orbit-bg-tertiary text-orbit-text-primary border border-orbit-border-primary hover:bg-orbit-bg-secondary hover:border-orbit-border-secondary active:bg-orbit-border-primary',
      ghost: 'text-orbit-text-secondary hover:text-orbit-text-primary hover:bg-orbit-bg-tertiary',
      danger: 'bg-orbit-accent-negative text-white hover:bg-red-600 active:bg-red-700',
    };

    const sizeClasses = {
      sm: 'px-3 py-1.5 text-sm',
      md: 'px-4 py-2.5 text-sm',
      lg: 'px-6 py-3 text-base',
    };

    const widthClass = fullWidth ? 'w-full' : '';

    return (
      <button
        ref={ref}
        className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${widthClass} ${className}`}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {!loading && children}
      </button>
    );
  }
);

Button.displayName = 'Button';