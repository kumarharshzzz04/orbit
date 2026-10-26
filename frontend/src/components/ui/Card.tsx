// ORBIT Frontend - Card Components
// Reusable card components for data display

import { HTMLAttributes, forwardRef } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ children, variant = 'default', padding = 'md', hover = false, className = '', ...props }, ref) => {
    const variantClasses = {
      default: 'bg-orbit-bg-card border border-orbit-border-primary',
      elevated: 'bg-orbit-bg-card border border-orbit-border-primary shadow-lg shadow-cyan-500/5',
      outlined: 'bg-transparent border-2 border-orbit-border-secondary',
    };

    const paddingClasses = {
      none: '',
      sm: 'p-4',
      md: 'p-6',
      lg: 'p-8',
    };

    const hoverClass = hover ? 'hover:border-orbit-border-secondary transition-colors duration-200' : '';

    return (
      <div
        ref={ref}
        className={`${variantClasses[variant]} ${paddingClasses[padding]} rounded-xl ${hoverClass} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {}

export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ children, className = '', ...props }, ref) => (
    <div ref={ref} className={`mb-4 ${className}`} {...props}>
      {children}
    </div>
  )
);

CardHeader.displayName = 'CardHeader';

export interface CardTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  subtitle?: string;
}

export const CardTitle = forwardRef<HTMLHeadingElement, CardTitleProps>(
  ({ children, subtitle, className = '', ...props }, ref) => (
    <div {...props}>
      <h3 ref={ref} className={`text-orbit-text-primary font-semibold text-lg ${className}`}>
        {children}
      </h3>
      {subtitle && <p className="text-orbit-text-tertiary text-sm mt-0.5">{subtitle}</p>}
    </div>
  )
);

CardTitle.displayName = 'CardTitle';

export interface CardContentProps extends HTMLAttributes<HTMLDivElement> {}

export const CardContent = forwardRef<HTMLDivElement, CardContentProps>(
  ({ children, className = '', ...props }, ref) => (
    <div ref={ref} className={className} {...props}>
      {children}
    </div>
  )
);

CardContent.displayName = 'CardContent';

export interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {}

export const CardFooter = forwardRef<HTMLDivElement, CardFooterProps>(
  ({ children, className = '', ...props }, ref) => (
    <div
      ref={ref}
      className={`mt-4 pt-4 border-t border-orbit-border-primary/50 flex items-center gap-3 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
);

CardFooter.displayName = 'CardFooter';