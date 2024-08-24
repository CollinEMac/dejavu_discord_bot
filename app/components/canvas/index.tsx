import { useEffect, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { setCanvasSize } from '../store/actions';
import { getCanvasSize } from '../store/selectors';

function Canvas({ background }: { background: 'japmic' | 'iphone' }) {
  const dispatch = useAppDispatch();
  const canvasSize = useAppSelector(getCanvasSize);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.canvas.width = canvasSize.width;
        ctx.canvas.height = canvasSize.height;
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvasSize.width, canvasSize.height);
      }
    }
  }, [canvasSize]);

  const drawJapmicText = useCallback((ctx: CanvasRenderingContext2D) => {
    ctx.font = '48px Arial';
    ctx.textAlign = 'center';

    if (background === 'japmic') {
      ctx.fillStyle = 'black';
      ctx.textBaseline = 'top';
      ctx.fillText('japmic', canvasSize.width / 2, 20);
    } else if (background === 'iphone') {
      ctx.fillStyle = 'white';
      ctx.textBaseline = 'middle';
      ctx.fillText('japmic', canvasSize.width / 2, canvasSize.height / 2);
    }
  }, [canvasSize, background]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        drawJapmicText(ctx);
      }
    }
  }, [drawJapmicText]);

  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas) {
        const width = canvas.offsetWidth;
        const height = canvas.offsetHeight;
        dispatch(setCanvasSize({ width, height }));
      }
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [dispatch]);

  return <canvas ref={canvasRef} />;
}

export default Canvas;