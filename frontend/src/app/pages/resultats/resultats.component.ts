import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { LabmindApiService } from '../../services/labmind-api.service';

@Component({
  selector: 'app-resultats',
  imports: [RouterLink],
  templateUrl: './resultats.component.html',
  styleUrl: './resultats.component.css'
})
export class ResultatsComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  api = inject(LabmindApiService);

  taskId = '';
  task: any = null;
  deletedMessage = '';
  mockPdfNotice = false;

  ngOnInit() {
    this.taskId = this.route.snapshot.paramMap.get('id') || '';
    const stateTask = history.state?.task;

    if (stateTask && stateTask.task_id === this.taskId) {
      this.task = stateTask;
    } else if (this.taskId) {
      this.api.getTask(this.taskId).subscribe({
        next: (task) => {
          if (task.status !== 'done') {
            this.router.navigate(['/attente', this.taskId]);
          } else {
            this.task = task;
          }
        },
        error: (err) => {
          this.router.navigate(['/erreur'], { state: { error: this.api.formatError(err) } });
        }
      });
    }
  }

  get hasConfidence(): boolean {
    return (this.task?.parameters || []).some(
      (p: any) => p.confidence !== null && p.confidence !== undefined
    );
  }

  get hasExplanations(): boolean {
    const exp = this.task?.explanations;
    if (!exp) return false;
    return Boolean(exp.summary) || (exp.parameter_explanations?.length ?? 0) > 0;
  }

  get parameterExplanations(): any[] {
    return this.task?.explanations?.parameter_explanations || [];
  }

  getParameterName(code: string): string {
    const found = (this.task?.parameters || []).find((p: any) => p.code === code);
    return found ? `${found.name_printed} (${code})` : code;
  }

  getSourceById(sourceId: string): any {
    return (this.task?.sources || []).find((s: any) => s.source_id === sourceId) || null;
  }

  formatCategory(cat: string): string {
    const labels: Record<string, string> = {
      nfs: 'NFS',
      bilan_martial: 'Bilan martial',
      bilan_glycemique: 'Bilan glycémique',
      bilan_lipidique: 'Bilan lipidique',
      bilan_hepatique: 'Bilan hépatique',
      bilan_renal: 'Bilan rénal'
    };
    return labels[cat] || cat;
  }

  countStatus(status: string): number {
    return (this.task?.parameters || []).filter((p: any) => p.status === status).length;
  }

  getStatusLabel(status: string): string {
    switch (status) {
      case 'within_reference':
        return 'Dans la fourchette du laboratoire';
      case 'below_reference':
        return 'En dessous de la fourchette';
      case 'above_reference':
        return 'Au-dessus de la fourchette';
      case 'reference_unavailable':
        return 'Fourchette indisponible';
      case 'value_unavailable':
        return 'Valeur indisponible';
      case 'not_analyzed':
        return 'Non analysé';
      default:
        return status;
    }
  }

  getBadgeClass(status: string): string {
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

  getExplanationStatusLabel(status: string): string {
    switch (status) {
      case 'grounded':
        return 'Explication sourcée';
      case 'insufficient_sources':
        return 'Sources insuffisantes ou modèle local indisponible';
      case 'not_analyzed':
        return 'Paramètre non analysé';
      default:
        return status;
    }
  }

  formatReference(ref: any): string {
    if (!ref || (ref.min === null && ref.max === null)) {
      return 'Non fournie';
    }
    if (ref.min !== null && ref.max !== null) {
      return `${ref.min} – ${ref.max}`;
    }
    if (ref.min === null && ref.max !== null) {
      return `< ${ref.max}`;
    }
    return `> ${ref.min}`;
  }

  imprimer() {
    window.print();
  }

  telechargerPdfMock() {
    this.mockPdfNotice = true;
  }

  supprimerDonnees() {
    this.api.deleteTask(this.taskId).subscribe({
      next: () => {
        this.deletedMessage = 'Vos données et résultats ont été supprimés.';
        this.task = null;
      },
      error: (err) => {
        this.router.navigate(['/erreur'], { state: { error: this.api.formatError(err) } });
      }
    });
  }
}
