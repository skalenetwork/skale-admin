import React from 'react'
import {Link} from 'react-router-dom'

import {Button} from 'rmwc/Button';
import classes from './SkaleButton.scss';

const sizes = ['sm', 'md', 'lg'];

export default class SkaleButton extends React.Component {
  render() {
    if (!sizes.includes(this.props.size)){
      // todo: raise an error
    }
    return (
      <Button raised {...this.props} className={`skale-btn skale-btn-${this.props.size} skale-btn-${this.props.color} ${this.props.className}`}>{this.props.children}</Button>
    )
  }
}

SkaleButton.defaultProps = {
  size: 'md',
  color: 'accent'
};
