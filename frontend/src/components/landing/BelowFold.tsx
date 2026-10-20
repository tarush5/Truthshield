/**
 * Everything on the landing page below the hero, as its own chunk: it
 * downloads in parallel with the hero instead of delaying it. Landing starts
 * the import as soon as its own module runs.
 */
import { BigType } from '@/components/landing/BigType';
import { Catches } from '@/components/landing/Catches';
import { CtaBand } from '@/components/landing/CtaBand';
import { Engines } from '@/components/landing/Engines';
import { Faq } from '@/components/landing/Faq';
import { Footer as SiteFooter } from '@/components/landing/Footer';
import { Why } from '@/components/landing/Why';

export default function BelowFold() {
  return (
    <>
      <Catches />
      <Why />
      <BigType />
      <Engines />
      <Faq />
      <CtaBand />
    </>
  );
}

export function Footer() {
  return <SiteFooter />;
}
