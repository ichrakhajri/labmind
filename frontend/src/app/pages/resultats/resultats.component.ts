import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LabmindApiService } from '../../services/labmind-api.service';

@Component({
  selector: 'app-resultats',
  imports: [CommonModule, RouterLink],
  templateUrl: './resultats.component.html',
  styleUrl: './resultats.component.css'
})
export class ResultatsComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(LabmindApiService);

  taskId = '';
  task: any = null;
  pdfUrl = '';
  isDeleting = false;
  deleted = false;
  errorMessage = '';

  ngOnInit(): void {
    this.taskId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.taskId) {
      this.router.navigate(['/erreur']);
      return;
    }
    this.pdfUrl = this.api.getReportPdfUrl(this.taskId);

    this.api.getTask(this.taskId).subscribe({
      next: (data) => {
        if (data?.status === 'processing' || data?.status === 'received') {
          this.router.navigate(['/attente', this.taskId]);
        } else if (data?.status === 'waiting_for_user') {
          this.router.navigate(['/verification', this.taskId]);
        } else if (data?.status === 'error') {
          const message = data?.errors?.[0]?.message || 'Impossible de traiter ce document.';
          this.router.navigate(['/erreur'], { state: { message } });
        } else {
          this.task = data;
        }
      },
      error: (err) => {
        const formatted = this.api.formatError(err);
        this.router.navigate(['/erreur'], { state: { message: formatted.message } });
      }
    });
  }

  get isImageDoc(): boolean {
    const name: string = this.task?.document?.filename || '';
    return /.(png|jpe?g)$/i.test(name);
  }

  formatRef(ref: any): string {
    if (!ref) return '';
    if (ref.min !== null && ref.min !== undefined && ref.max !== null && ref.max !== undefined) {
      return `(${ref.min} – ${ref.max})`;
    }
    if (ref.max !== null && ref.max !== undefined) {
      return `(< ${ref.max})`;
    }
    if (ref.min !== null && ref.min !== undefined) {
      return `(> ${ref.min})`;
    }
    return '';
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'within_reference':
        return 'Dans la fourchette';
      case 'below_reference':
        return 'En dessous';
      case 'above_reference':
        return 'Au-dessus';
      case 'reference_unavailable':
        return 'Réf. absente';
      case 'value_unavailable':
        return 'Valeur absente';
      default:
        return 'Non analysé';
    }
  }

  statusClass(status: string): string {
    switch (status) {
      case 'within_reference':
        return 'badge badge-dans';
      case 'below_reference':
        return 'badge badge-sous';
      case 'above_reference':
        return 'badge badge-au-dessus';
      default:
        return 'badge badge-indispo';
    }
  }

  get readableExplanations(): Array<{ name: string; text: string }> {
    const items = this.task?.explanations?.parameter_explanations || [];
    const params = this.task?.parameters || [];
    return items
      .filter((exp: any) => exp?.status === 'grounded' && exp?.text)
      .map((exp: any) => {
        const match = params.find((p: any) => p.code === exp.code);
        return {
          name: match?.name_printed || exp.code,
          text: exp.text
        };
      });
  }

  get lifestyleInfo(): { text: string; isGrounded: boolean } | null {
    const info = this.task?.explanations?.lifestyle_info;
    if (!info?.text) return null;
    return {
      text: info.text,
      isGrounded: info.status === 'grounded'
    };
  }

  get consultationQuestions(): string[] {
    return this.task?.explanations?.consultation_questions || [];
  }

  deleteData(): void {
    if (this.isDeleting) return;
    this.isDeleting = true;
    this.errorMessage = '';

    this.api.deleteTask(this.taskId).subscribe({
      next: () => {
        this.isDeleting = false;
        this.deleted = true;
      },
      error: (err) => {
        this.isDeleting = false;
        this.errorMessage = this.api.formatError(err).message;
      }
    });
  }
}
